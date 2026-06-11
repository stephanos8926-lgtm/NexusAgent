# Secrets Sync — `.env` Synchronization via SSH

`scripts/sync-secrets.py` copies your local `.env` file to one or more remote
servers over SSH, creating a timestamped backup of the existing remote `.env`
before overwriting it.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Setup](#setup)
   - [SSH Key Configuration](#ssh-key-configuration)
   - [Server Configuration](#server-configuration)
3. [Usage](#usage)
   - [Basic Sync](#basic-sync)
   - [Dry Run](#dry-run)
   - [Custom Remote Path](#custom-remote-path)
   - [Custom Config Path](#custom-config-path)
4. [Adding & Rotating Secrets](#adding--rotating-secrets)
5. [Adding a New Server](#adding-a-new-server)
6. [Troubleshooting](#troubleshooting)

---

## Prerequisites

| Requirement | Details |
|-------------|---------|
| **Python**  | ≥ 3.10 |
| **PyYAML** | `pip install pyyaml` |
| **SSH**     | System `ssh` and `scp` binaries (OpenSSH) |
| **SSH Key** | Ed25519 (or RSA) keypair with access to the target server |

---

## Setup

### SSH Key Configuration

1. **Generate a key** (if you don't already have one):

   ```bash
   ssh-keygen -t ed25519 -C "nexusagent-secrets-sync" -f ~/.ssh/id_ed25519
   ```

2. **Copy the public key** to the target server:

   ```bash
   ssh-copy-id -i ~/.ssh/id_ed25519.pub sysop@rapidwebs-01
   ```

3. **Verify passwordless login** works:

   ```bash
   ssh -i ~/.ssh/id_ed25519 sysop@rapidwebs-01 echo "ok"
   ```

   If this hangs or prompts for a password, fix SSH access before proceeding.

### Server Configuration

Edit `config/secrets-sync.yaml` to define your servers:

```yaml
servers:
  rapidwebs-01:
    host: rapidwebs-01          # hostname or IP
    user: sysop                 # SSH user
    path: /home/sysop/Workspaces/NexusAgent   # remote project root
    ssh_key: ~/.ssh/id_ed25519  # path to private key
```

Each top-level key under `servers` becomes a valid argument for `--server`.

---

## Usage

### Basic Sync

```bash
python scripts/sync-secrets.py --server rapidwebs-01
```

This will:

1. Read the local `.env` from the repository root.
2. SSH to `sysop@rapidwebs-01`.
3. Back up the existing remote `.env` to `.env.bak.<timestamp>`.
4. Upload the local `.env` with `600` permissions.
5. Verify permissions and file size.

### Dry Run

Preview every SSH/SCP command without making changes:

```bash
python scripts/sync-secrets.py --server rapidwebs-01 --dry-run
```

### Custom Remote Path

Override the `path` from config (useful for testing or non-standard layouts):

```bash
python scripts/sync-secrets.py --server rapidwebs-01 --remote-path /opt/myapp
```

### Custom Config Path

Use a non-default configuration file:

```bash
python scripts/sync-secrets.py --server staging --config /path/to/other-config.yaml
```

---

## Adding & Rotating Secrets

1. **Edit your local `.env`** in the repository root:

   ```bash
   nano .env
   ```

2. **Sync to the target server(s):**

   ```bash
   python scripts/sync-secrets.py --server rapidwebs-01
   ```

3. **Verify on the remote:**

   ```bash
   ssh sysop@rapidwebs-01 "cat .env"
   ```

4. **If something goes wrong**, restore the backup:

   ```bash
   ssh sysop@rapidwebs-01 "cp .env.bak.<timestamp> .env"
   ```

> **Tip:** Backups are never automatically deleted. Periodically clean old
> `.env.bak.*` files on remote servers to avoid clutter.

---

## Adding a New Server

1. Ensure SSH key-based access works (see [Setup](#setup)).
2. Add an entry to `config/secrets-sync.yaml`:

   ```yaml
   servers:
     rapidwebs-01:
       host: rapidwebs-01
       user: sysop
       path: /home/sysop/Workspaces/NexusAgent
       ssh_key: ~/.ssh/id_ed25519

     my-new-server:
       host: 203.0.113.42
       user: deploy
       path: /opt/nexusagent
       ssh_key: ~/.ssh/id_ed25519
   ```

3. Test with `--dry-run` first:

   ```bash
   python scripts/sync-secrets.py --server my-new-server --dry-run
   ```

---

## Troubleshooting

### `ssh: connect to host … port 22: Connection refused`

- Verify the server is reachable: `ping <host>`.
- Check that SSH is running on the remote: `systemctl status sshd`.
- Confirm firewall rules allow port 22.

### `Permission denied (publickey)`

- Ensure the public key is in `~/.ssh/authorized_keys` on the remote.
- Check key permissions: `chmod 600 ~/.ssh/id_ed25519`.
- Test manually: `ssh -i ~/.ssh/id_ed25519 user@host echo ok`.

### `Local .env not found`

The script expects `.env` in the repository root
(`/home/sysop/Workspaces/NexusAgent/.env`). Create it or run the script from
the correct working directory.

### `Local .env is empty — aborting`

The script refuses to upload an empty file to avoid wiping remote secrets.
Add at least one variable to `.env` before syncing.

### `Remote permissions are 644, expected 600`

The upload succeeded but `chmod 600` didn't take effect. Check that the SSH
user owns the remote file and that the filesystem doesn't have restrictions
(e.g., `noexec` mounts won't affect this, but certain ACLs might).

### `scp failed: …`

- Verify `scp` is installed on both local and remote.
- Check disk space on the remote: `df -h /`.
- Ensure the remote parent directory exists and is writable.

---

## Security Notes

- The script sets `600` (owner-read-write-only) permissions on the remote
  `.env` file.
- Backups (`.env.bak.*`) inherit the permissions of the original file at copy
  time — consider tightening them manually if needed.
- **Never commit `.env` or `secrets-sync.yaml` with real credentials to
  version control.** Add them to `.gitignore`.
