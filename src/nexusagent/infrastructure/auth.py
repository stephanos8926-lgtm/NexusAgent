"""Authentication and API key management.

Provides ``AuthManager`` for Fernet-encrypted API key storage with PBKDF2
key derivation, plus module-level ``get_auth_manager`` / ``set_auth_manager``
singleton accessors.
"""

import base64
import json
import logging
import os
import secrets
from pathlib import Path

from cryptography.fernet import Fernet
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from nexusagent.infrastructure.config import settings

logger = logging.getLogger(__name__)


class AuthManager:
    """Manages Fernet-encrypted API key storage using PBKDF2 key derivation.

    Reads configuration paths from ``settings.auth`` and provides
    ``save_key`` / ``get_key`` for encrypted key persistence.
    """

    def __init__(self):
        """Initialize the auth manager with paths from the global settings."""
        self.master_secret_path = Path(settings.auth.master_secret_path)
        self.keystore_path = Path(settings.auth.keystore_path)
        self.salt_path = Path(settings.auth.salt_path)

    def _get_salt(self) -> bytes:
        """Retrieves or creates a random salt for KDF."""
        if not self.salt_path.exists():
            salt = secrets.token_bytes(16)
            with open(self.salt_path, "wb") as f:
                f.write(salt)
            os.chmod(self.salt_path, 0o600)
            return salt

        with open(self.salt_path, "rb") as f:
            return f.read()

    def _get_master_key(self) -> bytes:
        """Retrieves the master secret and derives a 32-byte key for Fernet using a unique salt.

        Supports reading the master secret from the NEXUS_AUTH_MASTER_SECRET environment
        variable as an alternative to the on-disk file. This is useful for containerized
        deployments and secrets managers.
        """
        # Prefer env var over on-disk file (supports secrets managers / containers)
        env_secret = os.environ.get("NEXUS_AUTH_MASTER_SECRET")
        if env_secret:
            secret = env_secret.strip().encode()
        else:
            if not self.master_secret_path.exists():
                raise FileNotFoundError(
                    f"Master secret not found at {self.master_secret_path}. "
                    "Run initialization wizard or set NEXUS_AUTH_MASTER_SECRET env var."
                )
            with open(self.master_secret_path, "rb") as f:
                secret = f.read().strip()

        salt = self._get_salt()

        # Derive a fixed-length key from the master secret and the installation-specific salt
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=settings.auth.kdf_iterations,
            backend=default_backend(),
        )
        return base64.urlsafe_b64encode(kdf.derive(secret))

    def _get_fernet(self) -> Fernet:
        if not hasattr(self, "_fernet") or self._fernet is None:
            self._fernet = Fernet(self._get_master_key())
        return self._fernet

    def initialize_wizard(self, force: bool = False):
        """Creates the master secret if it doesn't exist.
        Sets restricted file permissions (600).
        """
        if self.master_secret_path.exists() and not force:
            return "Master secret already exists."

        # Generate high-entropy random secret
        secret = secrets.token_urlsafe(32)

        # Create file with restricted permissions
        with open(self.master_secret_path, "wb") as f:
            f.write(secret.encode())

        os.chmod(self.master_secret_path, 0o600)

        # Also ensure salt exists
        self._get_salt()

        return f"Master secret initialized successfully. Path: {self.master_secret_path}"

    def save_key(self, service: str, key: str):
        """Encrypts and saves a service API key to the keystore."""
        fernet = self._get_fernet()
        encrypted_key = fernet.encrypt(key.encode()).decode()

        keystore = self._load_keystore()
        keystore[service] = encrypted_key
        self._save_keystore(keystore)

    def get_key(self, service: str) -> str | None:
        """Retrieves and decrypts a service API key."""
        try:
            fernet = self._get_fernet()
            keystore = self._load_keystore()
            encrypted_key = keystore.get(service)
            if not encrypted_key:
                return None
            return fernet.decrypt(encrypted_key.encode()).decode()
        except Exception as e:
            logger.warning(f"Failed to decrypt key for '{service}': {type(e).__name__}")
            return None

    def _load_keystore(self) -> dict:
        if not self.keystore_path.exists():
            return {}
        with open(self.keystore_path) as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}

    def _save_keystore(self, keystore: dict):
        with open(self.keystore_path, "w") as f:
            json.dump(keystore, f, indent=4)
        os.chmod(self.keystore_path, 0o600)


# Module-level singleton (lazy, injectable)
_auth_manager_instance: AuthManager | None = None


def get_auth_manager() -> AuthManager:
    """Get or create the module-level AuthManager singleton."""
    global _auth_manager_instance
    if _auth_manager_instance is None:
        _auth_manager_instance = AuthManager()
    return _auth_manager_instance


def set_auth_manager(instance: AuthManager) -> None:
    """Override the module-level AuthManager singleton (for testing/dependency injection)."""
    global _auth_manager_instance
    _auth_manager_instance = instance


# Backward-compatible alias — deprecated, use get_auth_manager()
auth_manager = get_auth_manager()
