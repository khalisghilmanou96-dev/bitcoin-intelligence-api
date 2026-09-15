# Security

Bitcoin Intelligence API V2.1 is currently intended primarily for development and self-hosted deployments.

Before exposing an instance to the public Internet, production deployments should implement appropriate security controls, including:

- HTTPS
- API authentication
- rate limiting
- request quotas
- restrictive CORS configuration
- secure secret management
- dedicated PostgreSQL credentials
- structured logging and monitoring
- resource and LLM usage monitoring
- crawler SSRF protection
- per-domain crawl rate limits

Never commit `.env`, API credentials, private keys, database passwords, or other production secrets to the repository.

Security issues should be reported privately to the project maintainers rather than disclosed through a public issue.