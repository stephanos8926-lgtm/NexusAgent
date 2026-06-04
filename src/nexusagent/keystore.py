import json
import os
from pathlib import Path

from cryptography.fernet import Fernet


class Keystore:
    def __init__(self, path: str = ".nexus_keystore"):
        self.path = Path(path)
        key = os.environ.get("NEXUS_KEYSTORE_KEY")
        if not key:
            raise ValueError("NEXUS_KEYSTORE_KEY env var not set")
        self.fernet = Fernet(key.encode())

        if not self.path.exists():
            self.path.touch(mode=0o600)
            self._save_data({})

        # Ensure correct permissions
        os.chmod(self.path, 0o600)

    def _save_data(self, data: dict):
        json_data = json.dumps(data).encode()
        encrypted_data = self.fernet.encrypt(json_data)
        with open(self.path, "wb") as f:
            f.write(encrypted_data)
        os.chmod(self.path, 0o600)

    def _load_data(self) -> dict:
        with open(self.path, "rb") as f:
            encrypted_data = f.read()
        if not encrypted_data:
            return {}
        decrypted_data = self.fernet.decrypt(encrypted_data)
        return json.loads(decrypted_data.decode())

    def save_secret(self, name: str, secret: str):
        data = self._load_data()
        data[name] = secret
        self._save_data(data)

    def get_secret(self, name: str) -> str:
        data = self._load_data()
        return data.get(name)
