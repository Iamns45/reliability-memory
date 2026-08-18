# Security policy

## Supported version

Security updates are applied to the current `main` branch.

## Reporting a vulnerability

Do not open a public issue for a suspected vulnerability or exposed credential. Use the repository's **Security → Report a vulnerability** workflow so maintainers can investigate privately.

Include the affected endpoint or component, reproduction steps, expected impact, and any suggested mitigation. Do not include real customer data or active credentials.

## Credential handling

- Keep `.env*` files, database URLs, service-account keys, certificates, and AWS exports out of Git.
- Store production database and Managed MCP credentials in AWS Secrets Manager.
- Rotate any credential that appears in terminal output, an issue, a pull request, or commit history.
- Use synthetic records only when reproducing a data-handling problem.
