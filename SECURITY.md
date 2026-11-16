# Security Policy

## Supported branch

Security fixes should target the default `main` branch unless a release branch is explicitly announced.

## Reporting a vulnerability

Please do not publish exploit details, credentials, access tokens, patient information or a proof-of-concept containing sensitive data in a public issue.

Use GitHub's private vulnerability reporting for this repository (Security tab → Report a vulnerability). If private reporting is unavailable, open a minimal public issue requesting a private contact channel without including the vulnerability details.

## Sensitive data

- Never submit real patient information or clinical system exports.
- Never commit `.env` files, credentials, tokens, private keys or production configuration.
- Treat logs, traces, vector-store payloads and test artifacts as potentially sensitive.
- The default Docker Compose profile is for local synthetic data only and is not approved for production or real patient data.

## Security boundaries

The FastAPI service is the enforcement point for identity, roles and patient grants. UI visibility and MCP tool descriptions do not replace server-side authorization. Report any cross-patient data exposure, token-validation bypass, privilege escalation, or unintended disclosure as a security vulnerability.

## Disclosure

Please allow maintainers reasonable time to investigate, reproduce, fix and coordinate disclosure before public release of vulnerability details.
