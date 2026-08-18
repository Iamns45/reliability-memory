# Contributing

Reliability Memory treats the deterministic permission boundary and verified outcome history as security-sensitive code. Keep changes small, explain their trust impact, and add tests for every policy or transaction behavior change.

## Local setup

```bash
npm ci
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r services/api/requirements-dev.txt
```

## Quality gate

Run the same checks used in CI before opening a pull request:

```bash
npm run check
npm run audit:prod
```

Use `npm run format` to apply the repository's TypeScript, CSS, YAML, Markdown, shell-adjacent, and Python formatting rules.

## Engineering expectations

- Keep Bedrock responsible for proposals only. Permission decisions remain deterministic.
- Never let pending or self-reported outcomes improve reliability.
- Keep external side effects outside CockroachDB transactions.
- Make write operations idempotent and retry the whole transaction on SQLSTATE `40001`.
- Treat SQLSTATE `40003` as ambiguous and reconcile by idempotency key before replay.
- Add a forward migration for schema changes; do not rely only on editing an existing migration.
- Do not commit credentials, connection strings, customer data, generated builds, or local caches.

## Pull requests

Include a concise problem statement, the chosen design, test evidence, and any operational or security impact. UI changes should remain accessible, responsive, and honest about whether the AWS runtime is connected.
