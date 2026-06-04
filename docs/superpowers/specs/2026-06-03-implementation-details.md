# Implementation Details: Production-Grade Foundation (2026-06-03)

## 1. Centralized Configuration System
Implemented in `src/nexusagent/config.py`, the new configuration system replaces basic environment lookups with a structured, validated approach.

### Architecture
- **Pydantic Models**: Uses nested `ServerConfig` and `ClientConfig` models to enforce type safety across the entire application.
- **Hierarchical Loading**: 
    1. Loads defaults from Pydantic.
    2. Overrides with values from `config/nexusagent.yaml`.
    3. Final override via environment variables.
- **Environment Variable Pattern**: 
    - Global settings: `NEXUS_LOG_LEVEL=DEBUG`
    - Nested settings: `NEXUS_SERVER__NATS_URL=nats://localhost:4222` (Double underscore denotes nesting).
- **Path Resolution**: Automatically resolves relative paths to absolute paths relative to the project root.

## 2. Secure Authentication & Keystore
Implemented in `src/nexusagent/auth.py`, providing a mechanism for managing third-party API keys without storing them in plaintext.

### Secret Wizard (`.master.secret`)
- On initialization, a high-entropy 32-byte random secret is generated.
- File permissions are set to `0600` (owner read/write only) immediately upon creation.

### Encryption Pipeline
- **KDF**: Uses `PBKDF2HMAC` with SHA-256 to derive a cryptographically strong 32-byte key from the master secret.
- **Algorithm**: Employs `cryptography.fernet` (AES-128 in CBC mode with HMAC-SHA256) for authenticated encryption of API keys.
- **Keystore**: Encrypted keys are stored in `keystore.json`, also locked to `0600` permissions.

### Workflow
1. `AuthManager.initialize_wizard()` $\rightarrow$ Setup master secret.
2. `AuthManager.save_key(service, key)` $\rightarrow$ Encrypt and store.
3. `AuthManager.get_key(service)` $\rightarrow$ Decrypt and return.
