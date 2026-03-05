# Security Policy

## Supported Versions

We actively support the following versions of NEXUS with security updates:

| Version | Supported          | Status |
| ------- | ------------------ | ------ |
| 2.0.x   | :white_check_mark: | Current stable release |
| 1.5.x   | :x:                | Legacy (deprecated) |
| < 1.5   | :x:                | No longer supported |

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

We take the security of NEXUS seriously. If you discover a security vulnerability, please follow these steps:

### 1. Report Privately

Email security details to: **kcaracozza@gmail.com**

Please include:
- Type of vulnerability
- Full paths of source file(s) related to the vulnerability
- Location of the affected source code (tag/branch/commit or direct URL)
- Step-by-step instructions to reproduce the issue
- Proof-of-concept or exploit code (if possible)
- Impact of the vulnerability

### 2. What to Expect

- **Acknowledgment**: We'll acknowledge receipt within 48 hours
- **Initial Assessment**: We'll provide an initial assessment within 7 days
- **Updates**: You'll receive updates on our progress every 7 days
- **Resolution**: We aim to resolve critical issues within 30 days
- **Disclosure**: We follow coordinated disclosure practices

### 3. Security Update Process

Once a vulnerability is confirmed:

1. **Patch Development**: We develop and test a fix
2. **Security Advisory**: We create a security advisory (kept private until release)
3. **Release**: We release a patched version
4. **Disclosure**: We publicly disclose the vulnerability details after the patch is available
5. **Credit**: We credit the reporter (unless they prefer to remain anonymous)

## Security Best Practices for Users

### API Keys & Credentials

- **Never commit API keys** to the repository
- Store all credentials in `.env` files (automatically gitignored)
- Use the config_manager for secure credential access
- Rotate API keys regularly

### Data Protection

- **Collections are local by default** - no cloud storage without explicit opt-in
- User data never leaves the machine unless cloud sync is enabled
- Database files contain sensitive information - restrict access
- Back up collections regularly but securely

### Hardware Safety

- **Arduino firmware** includes safety limits on motor duration
- LED brightness is capped to prevent damage
- Camera access requires explicit permission
- Serial ports are validated before use

### Network Security

- **API server** should only be exposed on trusted networks
- Use firewall rules to restrict access to port 5000
- Enable authentication for remote scanner access
- Use HTTPS in production deployments

## Known Security Considerations

### Current Architecture

1. **Local-First Design**: NEXUS is designed to run locally, minimizing attack surface
2. **No Authentication by Default**: Local GUI app doesn't require login
3. **API Server**: Optional component, should be secured if exposed to network
4. **Hardware Access**: Requires physical access to USB devices

### Planned Security Enhancements (Future Releases)

- [ ] API authentication and authorization
- [ ] Encrypted database option
- [ ] Cloud sync with end-to-end encryption
- [ ] Multi-user access control
- [ ] Audit logging for commercial deployments
- [ ] OAuth integration for marketplace features

## Third-Party Dependencies

NEXUS relies on several third-party libraries. We:

- Monitor dependencies for known vulnerabilities
- Update dependencies regularly
- Follow security advisories from:
  - [Python Security](https://www.python.org/news/security/)
  - [NumPy Security](https://numpy.org/doc/stable/dev/)
  - [Pillow Security](https://pillow.readthedocs.io/)
  - [OpenCV Security](https://opencv.org/)

## Secure Development Guidelines

Contributors should follow these security practices:

### Code Review

- All PRs require review before merging
- Security-sensitive changes require additional scrutiny
- Use GitHub security scanning tools

### Input Validation

- Sanitize all user inputs
- Validate file paths before access
- Check data types and ranges
- Use parameterized database queries

### Error Handling

- Don't expose sensitive information in error messages
- Log errors securely
- Fail securely (deny by default)

### Cryptography

- Use well-established libraries (don't roll your own)
- Follow current best practices for key management
- Use appropriate key lengths

## Responsible Disclosure

We appreciate the security research community and:

- Acknowledge researchers who report vulnerabilities responsibly
- Work with researchers to understand and fix issues
- Provide credit in security advisories (if desired)
- Support coordinated disclosure timelines

## Bug Bounty

We do not currently have a formal bug bounty program, but we:

- Greatly appreciate security research
- Acknowledge contributors in our security advisories
- Consider security reports for future bounty programs

## Contact

**Security Team**: kcaracozza@gmail.com

**PGP Key**: Available upon request

---

**Last Updated**: November 26, 2025

*This security policy is subject to change. Check back regularly for updates.*
