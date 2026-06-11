#!/usr/bin/env python3
"""
sync-secrets.py — Sync local .env files to remote servers via SSH.

Usage:
    python scripts/sync-secrets.py --server rapidwebs-01
    python scripts/sync-secrets.py --server rapidwebs-01 --dry-run
    python scripts/sync-secrets.py --server rapidwebs-01 --remote-path /opt/myapp
"""

import argparse
import datetime
import os
import sys
import subprocess
import tempfile

import yaml

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
DEFAULT_CONFIG_PATH = os.path.join(REPO_ROOT, "config", "secrets-sync.yaml")
LOCAL_ENV_PATH = os.path.join(REPO_ROOT, ".env")


def load_config(config_path: str) -> dict:
    """Load and validate the secrets-sync YAML configuration."""
    if not os.path.isfile(config_path):
        print(f"[ERROR] Config file not found: {config_path}", file=sys.stderr)
        sys.exit(1)

    with open(config_path, "r") as fh:
        config = yaml.safe_load(fh)

    if not config or "servers" not in config:
        print("[ERROR] Config is missing the 'servers' key.", file=sys.stderr)
        sys.exit(1)

    return config


def resolve_server(config: dict, server_name: str) -> dict:
    """Return the server entry by name, exiting on miss."""
    server = config["servers"].get(server_name)
    if server is None:
        available = ", ".join(config["servers"].keys())
        print(
            f"[ERROR] Server '{server_name}' not found in config. "
            f"Available: {available}",
            file=sys.stderr,
        )
        sys.exit(1)
    return server


# ---------------------------------------------------------------------------
# SSH helpers  (subprocess + system ssh for agent/key forwarding support)
# ---------------------------------------------------------------------------


def _ssh_cmd(server: dict, remote_cmd: str, dry_run: bool = False) -> list[str]:
    """Build an ssh command list from server config."""
    ssh_key = os.path.expanduser(server.get("ssh_key", "~/.ssh/id_ed25519"))
    cmd = [
        "ssh",
        "-i", ssh_key,
        "-o", "StrictHostKeyChecking=accept-new",
        "-o", "BatchMode=yes",
        "-o", "ConnectTimeout=10",
    ]
    user = server.get("user", "sysop")
    host = server["host"]
    cmd.append(f"{user}@{host}")
    cmd.append(remote_cmd)
    return cmd


def ssh_run(server: dict, remote_cmd: str, dry_run: bool = False) -> subprocess.CompletedProcess:
    """Execute a command on the remote server via SSH."""
    cmd = _ssh_cmd(server, remote_cmd, dry_run)
    if dry_run:
        print(f"  [dry-run] {' '.join(cmd)}")
        return subprocess.CompletedProcess(cmd, returncode=0, stdout="", stderr="")
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result


def ssh_upload_string(server: dict, data: str, remote_path: str, permissions: str = "600",
                       dry_run: bool = False) -> None:
    """Upload a string to a remote file via a temp file + scp."""
    tmp_fd, tmp_path = tempfile.mkstemp(prefix="sync_secrets_")
    try:
        os.write(tmp_fd, data.encode())
        os.close(tmp_fd)

        ssh_key = os.path.expanduser(server.get("ssh_key", "~/.ssh/id_ed25519"))
        user = server.get("user", "sysop")
        host = server["host"]

        if dry_run:
            print(f"  [dry-run] scp {tmp_path} -> {user}@{host}:{remote_path}")
            print(f"  [dry-run] chmod {permissions} {remote_path}")
            return

        # scp the temp file
        scp_cmd = [
            "scp",
            "-i", ssh_key,
            "-o", "StrictHostKeyChecking=accept-new",
            "-o", "BatchMode=yes",
            "-o", "ConnectTimeout=10",
            tmp_path,
            f"{user}@{host}:{remote_path}",
        ]
        result = subprocess.run(scp_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"[ERROR] scp failed: {result.stderr.strip()}", file=sys.stderr)
            sys.exit(1)

        # set permissions
        ssh_run(server, f"chmod {permissions} {remote_path}", dry_run=False)
    finally:
        os.unlink(tmp_path)


# ---------------------------------------------------------------------------
# Core sync logic
# ---------------------------------------------------------------------------


def sync(server_name: str, config_path: str, dry_run: bool = False,
         remote_path_override: str | None = None) -> None:
    """Main sync routine."""
    config = load_config(config_path)
    server = resolve_server(config, server_name)

    # --- read local .env ---------------------------------------------------
    if not os.path.isfile(LOCAL_ENV_PATH):
        print(f"[ERROR] Local .env not found at {LOCAL_ENV_PATH}", file=sys.stderr)
        sys.exit(1)

    with open(LOCAL_ENV_PATH, "r") as fh:
        env_content = fh.read()

    if not env_content.strip():
        print("[WARN] Local .env is empty — aborting to avoid wiping remote secrets.",
              file=sys.stderr)
        sys.exit(1)

    # --- determine remote paths --------------------------------------------
    base_remote = remote_path_override or server.get("path", f"/home/{server.get('user', 'sysop')}")
    remote_env = os.path.join(base_remote, ".env")
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    remote_backup = os.path.join(base_remote, f".env.bak.{timestamp}")

    print(f"[{server_name}] Syncing .env -> {remote_env}")

    # --- check remote .env exists & back up --------------------------------
    check = ssh_run(server, f"test -f {remote_env} && echo EXISTS || echo MISSING",
                    dry_run=dry_run)
    remote_exists = "EXISTS" in check.stdout

    if remote_exists:
        print(f"  Backing up remote .env -> {remote_backup}")
        ssh_run(server, f"cp {remote_env} {remote_backup}", dry_run=dry_run)
    else:
        print("  No existing remote .env — skipping backup.")

    # --- upload new .env ---------------------------------------------------
    print(f"  Uploading new .env (permissions 600)")
    ssh_upload_string(server, env_content, remote_env, permissions="600", dry_run=dry_run)

    # --- verify ------------------------------------------------------------
    if not dry_run:
        verify = ssh_run(server, f"stat -c '%a' {remote_env}")
        perms = verify.stdout.strip()
        if perms != "600":
            print(f"[WARN] Remote permissions are {perms}, expected 600.", file=sys.stderr)
        else:
            print("  ✓ Permissions verified (600)")

        size = ssh_run(server, f"wc -c < {remote_env}")
        print(f"  ✓ Uploaded {size.stdout.strip()} bytes")
    else:
        print("  [dry-run] Skipping verification.")

    print(f"[{server_name}] Done.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sync local .env to a remote server via SSH.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  %(prog)s --server rapidwebs-01
  %(prog)s --server rapidwebs-01 --dry-run
  %(prog)s --server rapidwebs-01 --remote-path /opt/myapp
  %(prog)s --server rapidwebs-01 --config /path/to/secrets-sync.yaml
""",
    )
    parser.add_argument(
        "--server", required=True,
        help="Target server name (must match a key in secrets-sync.yaml).",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show what would happen without making changes.",
    )
    parser.add_argument(
        "--remote-path",
        help="Override the remote project base path from config.",
    )
    parser.add_argument(
        "--config", default=DEFAULT_CONFIG_PATH,
        help=f"Path to secrets-sync.yaml (default: {DEFAULT_CONFIG_PATH}).",
    )
    args = parser.parse_args()

    sync(
        server_name=args.server,
        config_path=args.config,
        dry_run=args.dry_run,
        remote_path_override=args.remote_path,
    )


if __name__ == "__main__":
    main()
