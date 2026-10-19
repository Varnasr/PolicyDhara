# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in PolicyDhara, please report it responsibly.

**Email:** care@pinpointventures.in

**Please do NOT open a public issue for security vulnerabilities.**

### What to include
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

### Response Timeline
- **Acknowledgement:** Within 48 hours
- **Assessment:** Within 5 business days
- **Resolution:** Within 7 days for critical issues

## Scope

The following are in scope:
- XSS vulnerabilities in the static site
- Data pipeline injection (malicious feed content)
- API key or credential exposure
- GitHub Actions workflow security issues
- RSS/feed parsing vulnerabilities
- Email digest injection

## Out of Scope
- DDoS attacks
- Social engineering
- Third-party service vulnerabilities (Buttondown, GitHub)
- Issues in upstream data sources

## Security Architecture

PolicyDhara processes data from 20+ government sources:
- All feed content is sanitized before rendering
- GitHub Actions run in isolated environments
- No user-submitted data is accepted directly
- Static site has no server-side execution
