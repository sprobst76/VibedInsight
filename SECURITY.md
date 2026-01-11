# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.3.x   | :white_check_mark: |
| < 0.3   | :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability within VibedInsight, please follow these steps:

1. **Do not** open a public GitHub issue
2. Send a detailed report to the project maintainer via GitHub private message
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

## Security Considerations

### Self-Hosted Nature

VibedInsight is designed to be self-hosted, meaning:

- **Your data stays on your server** - No third-party data collection
- **You control access** - Configure your own authentication and firewall rules
- **Local AI processing** - Ollama runs locally, no data sent to external AI services

### Recommended Security Practices

#### Backend Deployment

```bash
# Use strong database passwords
POSTGRES_PASSWORD=$(openssl rand -base64 32)

# Enable HTTPS via Traefik
# Never expose the backend without TLS

# Restrict network access
# Only expose necessary ports (443 for HTTPS)
```

#### Network Security

- Deploy behind a reverse proxy (Traefik recommended)
- Use valid TLS certificates (Let's Encrypt)
- Consider IP whitelisting for personal use
- Use a VPN for remote access

#### Database Security

- Use strong, unique passwords
- Regular backups with encryption
- Keep PostgreSQL updated

#### Application Security

- Keep dependencies updated
- Review Docker images regularly
- Monitor logs for suspicious activity

## Known Security Limitations

1. **No built-in authentication** (v0.3.x) - Relies on network-level security
2. **API tokens** - Not yet implemented; planned for v0.4.x
3. **Rate limiting** - Basic implementation via Traefik middleware

## Security Roadmap

- [ ] JWT-based authentication
- [ ] Per-user API tokens
- [ ] Encrypted vault entries
- [ ] Audit logging
- [ ] 2FA support

## Dependencies

We regularly update dependencies to patch security vulnerabilities:

```bash
# Backend
pip install --upgrade pip
pip install -e ".[dev]" --upgrade

# Flutter
flutter pub upgrade
```

## Acknowledgments

We appreciate responsible disclosure of security issues. Contributors who report
valid security vulnerabilities will be acknowledged (with permission) in release notes.
