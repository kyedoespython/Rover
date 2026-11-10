# Rover security review summary

Review date: 2026-11-10
Review type: source review; deployment verification is still required

## Finding

| # | Severity | File | Lines | Vulnerability | Confidence |
|---|----------|------|-------|---------------|------------|
| 1 | 🟡 MEDIUM | docker-compose.yml | 6-8, 44-47 | The web service was initially published over plain HTTP. It is now Compose-network-only behind Nginx HTTPS; live deployment configuration still needs verification. | 8/10 |

The mitigation requires a valid `ROVER_DOMAIN`, DNS pointing to the deployment host, ports 80 and 443 reaching Nginx, successful certificate issuance, and no external firewall or port-forward rule exposing the web container directly. The live deployment has not been tested.

## Recommended hardening

- Keep development-only source mounts and Gunicorn reload behavior out of production deployments.
- Add account/session-scoped throttling for repeated verification-code failures, while avoiding account-lockout denial of service.
- Require a separate, stable encryption key for stored Ollama credentials and plan secure backup and rotation.
- Add and test response security headers, including a CSP compatible with the application's templates.
- Verify TLS, firewalls, secret management, databases, Redis, SMTP, Ollama, and backup controls in the actual deployment environment.

## Scope

This was a read-only source review, not penetration testing or an audit of live infrastructure, dependencies, secrets, or service configuration. No other exploitable application-code issue was substantiated in the reviewed source.
