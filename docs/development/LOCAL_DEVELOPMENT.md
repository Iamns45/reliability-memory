# Local development

> Status: Current
>
> Audience: Software engineers
>
> Owner: Reliability Memory engineering maintainers
>
> Last reviewed: 2026-08-16

## Prerequisites

- Node.js 22.13 or newer
- Python 3.13
- Docker only when running local CockroachDB

## Install

```bash
npm ci
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r services/api/requirements-dev.txt
```

Copy any required configuration names from `.env.example` into your shell environment. Local secret files are ignored by source control.

## Development modes

### UI plus credential-free API behavior

```bash
npm run dev
```

Open `http://localhost:3000`. Runtime calls that execute inside the local web bundle use deterministic, synthetic behavior and require no cloud credentials.

### API with deterministic in-memory adapters

```bash
source .venv/bin/activate
uvicorn services.api.app.main:app --reload --port 8000
```

Keep `USE_BEDROCK=false` and leave `DATABASE_URL` empty. Open `http://localhost:8000/docs` for the generated API explorer.

### API with local CockroachDB

```bash
docker compose up --build
```

This starts CockroachDB, applies migrations `001` through `011`, seeds the 26-case consumer and enterprise evidence catalog, and runs the API on `http://localhost:8000`. The CockroachDB console is at `http://localhost:8080`.

## Engineering workflow

1. Make the smallest coherent change.
2. Add or update a forward-only migration for schema changes.
3. Update the relevant product, architecture, API, data, operations, security, or decision document.
4. Add tests at the lowest useful level and an integration test for a changed boundary.
5. Run `npm run format`.
6. Run `npm run check` and `npm run audit:prod`.
7. Include behavior, risk, migration, and test evidence in the change description.

## Repository map

| Path                  | Responsibility                                                             |
| --------------------- | -------------------------------------------------------------------------- |
| `app/`                | Judge-facing React workbench and browser API client                        |
| `aws-ui/`             | Static AWS UI entry point                                                  |
| `services/api/app/`   | FastAPI, one-node graph, agent runtime, policy, evidence, and repositories |
| `services/api/tests/` | Backend unit and integration tests                                         |
| `tests/`              | Static AWS UI artifact tests                                               |
| `agent-skills/`       | Five inspectable skills composed inside the one node                       |
| `db/migrations/`      | Ordered CockroachDB schema and synthetic demo data                         |
| `infra/aws/`          | AWS SAM infrastructure definition                                          |
| `scripts/`            | Migration, seeding, deployment, and documentation checks                   |
| `docs/`               | Canonical engineering and submission documentation                         |

## Change boundaries

- Bedrock may change a proposal, never permission.
- Browser input cannot override a catalog case's authoritative facts.
- Provider actions stay outside CockroachDB transactions.
- Pending and self-reported outcomes do not improve reliability.
- Review resume must remain idempotent because LangGraph re-enters the same node.
- Generated builds, credentials, connection strings, and caches must not be committed.
