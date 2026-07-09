# Security Policy

## Reporting a Vulnerability

Report security issues to **dev@rapidwebs.com** with subject `[NexusAgent SECURITY]`.

Please include:
- Description of the vulnerability
- Steps to reproduce
- Affected versions
- Potential impact

We aim to acknowledge within 48 hours and assess within 5 business days.

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | ✅ Active |

## Security Features

NexusAgent implements:
- Fernet-encrypted credential keystore (PBKDF2)
- WebSocket connection validation
- TOCTOU-attack-resistant approval workflow
- Rate-limited API endpoints
- Configurable permission scopes
