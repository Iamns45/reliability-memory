# Reliability Memory

An evidence-driven resolution agent that investigates a case, selects an eligible remedy, earns narrowly scoped permission, executes the authorized workflow, and learns only from verified outcomes.

- **Live application:** [https://d30n5k4sgmvobz.cloudfront.net/](https://d30n5k4sgmvobz.cloudfront.net/)
- **Runtime health:** [https://d30n5k4sgmvobz.cloudfront.net/health](https://d30n5k4sgmvobz.cloudfront.net/health)
- **Source:** [https://github.com/Iamns45/reliability-memory](https://github.com/Iamns45/reliability-memory)

## The problem

Customer-resolution automation often relies on vague rules such as “the amount is below $100” or “similar requests succeeded before.” Those signals are not enough to prove that a refund, replacement, repair, delivery recovery, account change, or infrastructure operation is correct.

Each problem requires different evidence. A duplicate charge needs a settled payment pair. A missing component needs package weight and bill-of-material records. An early product failure needs serial-linked diagnostics, warranty status, batch quality, and replacement inventory. A smoke report must enter a safety workflow regardless of value or model confidence.

Reliability Memory turns those differences into an explicit decision process. It asks:

1. What authoritative records prove the current problem?
2. Which remedies are eligible for this customer, product, contract, and risk context?
3. Which eligible remedy best balances the customer goal and company cost?
4. Has this exact context earned autonomous execution from independently verified outcomes?
5. Can the result be verified and stored without duplicating an external action?

## What it does

The application processes consumer and enterprise cases through one typed LangGraph node. The node coordinates a bounded sequence of ordinary Python capabilities:

1. Load the authoritative case and customer context from CockroachDB.
2. Build an issue-specific evidence packet.
3. Validate source authority, provenance, integrity, freshness, correlation, and conflicts.
4. Retrieve comparable verified episodes and corrections through CockroachDB vector search.
5. Compute the best eligible resolution from customer value, goal fit, company cost, and case limits.
6. Ask Amazon Bedrock Nova Lite for a structured, bounded proposal.
7. Apply deterministic policy outside the model.
8. Execute an idempotent multi-step workflow or pause with a complete human-review summary.
9. Verify the outcome independently and persist the episode, receipt, and future memory.

The model contributes reasoning and explanation. It cannot choose its own permission, bypass missing evidence, override a safety boundary, or turn similarity into proof.

## Decision outcomes

| Outcome  | Meaning                                                                                    |
| -------- | ------------------------------------------------------------------------------------------ |
| `AUTO`   | Current evidence is exact, the action is eligible, and this context has earned autonomy.   |
| `VERIFY` | The plan is supported, but customer confirmation or bounded analyst approval is required.  |
| `HUMAN`  | Evidence is incomplete, conflicting, high-impact, identity-sensitive, or safety-related.   |
| `DENY`   | Authoritative evidence proves the requested action is invalid; an appeal path is recorded. |

Selection and permission are separate decisions. A remedy can rank first economically and still require confirmation. A low-value request can remain human-owned, while a larger replacement can execute automatically when exact evidence and verified history support it.

## Trust model

### 1. Current evidence comes before memory

Historical similarity is consulted only after the current case passes its own eligibility checks. Missing, stale, tampered, mismatched, duplicated, or conflicting source records contract permission instead of being silently ignored.

### 2. The model proposes; deterministic code authorizes

The runtime resolution selector ranks eligible options using:

```text
selection score = goal fit × customer value ÷ company cost
```

Policy then evaluates the selected action, evidence grade, permission floor, risk, cost cap, verified outcomes, novelty, and human-approval requirements. Amazon Bedrock cannot set `AUTO`, `VERIFY`, `HUMAN`, or `DENY`.

### 3. Autonomy is contextual

Reliability is not one global score. Memory is partitioned by task and compared with the current account, contract, region, action, risk, evidence quality, and policy version. Success in a low-risk replacement context cannot authorize a safety escalation or privileged access change.

### 4. Human review continues the same investigation

When the graph interrupts, it already has the request, evidence, alternatives, economics, model proposal, policy reasons, recommended resolution, workflow plan, nearest episodes, and audit identifier. The analyst confirms, edits, or rejects that summary and resumes the same durable checkpoint.

An approved edit is stored as a correction and reusable lesson. It can change a later comparable proposal, but one correction does not automatically grant autonomy.

### 5. Execution is retry-safe and verifiable

Every provider operation receives an idempotency key and returns a stable reference. Database transactions remain short; external side effects stay outside them. Ambiguous database commits are reconciled before an operation is replayed. A repeated request returns the existing action instead of performing it twice.

## Architecture

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ Browser                                                                      │
│ React operations workbench: cases, evidence, decisions, workflows, receipts │
└───────────────────────────────┬──────────────────────────────────────────────┘
                                │ HTTPS
                                ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│ Amazon CloudFront                                                            │
│  / and static assets ──► private S3 origin                                   │
│  /health and /v1/* ────► Amazon API Gateway                                  │
└───────────────────────────────┬──────────────────────────────────────────────┘
                                ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│ AWS Lambda container                                                        │
│ FastAPI + one executable LangGraph node + AgentGraphState                    │
│                                                                              │
│  load facts → admit evidence → retrieve memory → select resolution           │
│      → Bedrock proposal → deterministic policy → interrupt or execute        │
│      → verify outcome → persist episode, receipt, and checkpoint             │
└───────────────┬────────────────────────┬───────────────────────┬──────────────┘
                │                        │                       │
                ▼                        ▼                       ▼
┌────────────────────────┐  ┌────────────────────────┐  ┌─────────────────────┐
│ CockroachDB Cloud      │  │ Amazon Bedrock         │  │ Workflow adapters   │
│ cases and evidence     │  │ Nova Lite proposals    │  │ payment, shipment,  │
│ policies and episodes  │  │ Titan V2 embeddings    │  │ repair, safety,     │
│ vector indexes         │  └────────────────────────┘  │ identity, platform  │
│ outcomes/corrections   │                              └──────────┬──────────┘
│ receipts/checkpoints   │                                         │
└────────────┬───────────┘                                         ▼
             │                                           independent verification
             ▼
┌────────────────────────┐
│ Managed MCP Server     │
│ read-only independent  │
│ episode + vector proof │
└────────────────────────┘

VERIFY / HUMAN ──► prefilled review ──► approve or edit ──► resume same checkpoint
```

The graph contains exactly one executable business node: `reliability_memory_agent`. `START` and `END` are LangGraph framework sentinels. Evidence evaluation, retrieval, policy, execution, verification, and learning are typed capabilities composed inside that node rather than additional graph nodes.

### Component responsibilities

| Component                         | Responsibility                                                                                  |
| --------------------------------- | ----------------------------------------------------------------------------------------------- |
| React workbench                   | Displays database-backed cases, source evidence, live SSE events, decisions, and audit records. |
| FastAPI                           | Validates requests, exposes catalog/run/resume/experiment routes, and streams backend events.   |
| One-node LangGraph                | Holds typed state and manages durable interrupt/resume through CockroachDB checkpoints.         |
| Deterministic resolution selector | Filters ineligible options and computes the best goal-adjusted value per company dollar.        |
| Amazon Bedrock Nova Lite          | Produces a structured proposal constrained by current evidence and eligible options.            |
| Deterministic policy              | Owns permission, cost boundaries, evidence requirements, safety rules, and reliability gates.   |
| CockroachDB Cloud                 | Stores operational facts, vector memory, corrections, audits, receipts, and checkpoints.        |
| Managed MCP Server                | Independently proves the persisted episode and vector-neighbor result before autonomous action. |
| Workflow adapters                 | Execute typed, idempotent operations and return provider-style references.                      |

More detail is available in the [system design](./docs/architecture/SYSTEM_DESIGN.md), [API contract](./docs/architecture/API_CONTRACT.md), and [data model](./docs/architecture/DATA_MODEL.md).

## How CockroachDB is used

CockroachDB is both the operational system of record and the durable memory layer. The runtime stores:

- customer, order, account, product, payment, contract, and infrastructure facts;
- case-specific evidence bundles and source provenance;
- policy versions and permission records;
- proposals, actions, outcomes, corrections, approvals, and audit receipts;
- LangGraph checkpoints for interrupt/resume;
- normalized 1,024-dimensional Titan embeddings for episodes and corrections.

### Distributed vector indexing

Episode text is embedded with Amazon Titan Text Embeddings V2. Task-prefixed vector indexes retrieve only compatible, verified experience. Operational columns and vectors remain in the same database, so an episode cannot be updated without its memory representation and audit state staying transactionally consistent.

Vector retrieval supplies evidence; it never grants permission by itself. Pending outcomes, self-reported success, and unrelated tasks do not improve reliability.

### Managed MCP verification

For an autonomous candidate, Lambda connects to the CockroachDB Cloud Managed MCP Server with a cluster-scoped service-account credential from AWS Secrets Manager. It calls only the read-only `select_query` tool to:

1. reload the persisted episode and permission;
2. repeat the vector-neighbor query through an independent path;
3. compare the episode, policy version, permission, and neighbor set;
4. produce a hashed verification receipt.

If the MCP proof is unavailable or does not match the direct database result, the runtime withholds the action and contracts permission to human review.

## How AWS is used

| AWS service       | Use                                                                                              |
| ----------------- | ------------------------------------------------------------------------------------------------ |
| Amazon Bedrock    | Nova Lite structured proposals and Titan Text Embeddings V2 memory vectors.                      |
| AWS Lambda        | FastAPI, LangGraph, evidence evaluation, policy, execution adapters, and verification.           |
| API Gateway       | Public HTTP and server-sent-event routes with throttling and access logging.                     |
| Amazon S3         | Private origin for the compiled React application.                                               |
| Amazon CloudFront | Public HTTPS, same-origin API routing, compression, no-cache API behavior, and security headers. |
| Secrets Manager   | CockroachDB connection URL and Managed MCP service-account key.                                  |
| CloudWatch Logs   | Request identifiers, routes, response status, duration, and Lambda diagnostics.                  |

The browser receives neither the database connection string nor the MCP credential.

## Different problems produce different workflows

The bundled catalog contains 26 database-backed cases: 18 consumer resolutions and 8 enterprise operations.

| Scenario                       | Evidence that matters                                                      | Resulting workflow                               |
| ------------------------------ | -------------------------------------------------------------------------- | ------------------------------------------------ |
| Duplicate settled charge       | Payment pair, currency, method, subscription, capture window, refund state | Refund the proven duplicate only                 |
| Cosmetic transit damage        | Inspection, product quality, customer goal, return economics               | Keep-item adjustment plus warranty after consent |
| Product fails after two days   | Serial telemetry, warranty, batch defects, unaffected inventory            | Replacement and defect-batch incident            |
| Missing laptop charger         | Package weight, bill of materials, shipment record                         | Ship the missing component                       |
| Missing delivery               | Carrier scan, delivery coordinates, address, claim pattern                 | Reship, investigate, or request human review     |
| Smoke on first use             | Safety report, product identity, batch, incident history                   | Safety escalation; never autonomous refund logic |
| Serial-number mismatch         | Order serial, submitted serial, ownership, warranty                        | Evidence-backed denial with appeal path          |
| Warranty-grace exception       | Failure date, warranty boundary, diagnostics, prior correction             | Prefilled repair review and correction replay    |
| Failed enterprise deployment   | Signed release, schema compatibility, health regression                    | Idempotent rollback                              |
| Privileged credential exposure | Audit logs, session evidence, blast radius                                 | Human-owned security containment                 |

Customer history is one review signal, never proof of wrongdoing. Product-level return rates can change the available offer, but they cannot replace case-specific evidence.

## Human interrupt and resume

A supervised case pauses after investigation, not before it. The review packet contains:

- customer request and goal;
- admitted and blocked evidence sources;
- selected remedy and all eligible alternatives;
- customer-value and company-cost breakdowns;
- model proposal and deterministic policy reasons;
- nearest verified episode identifiers;
- exact workflow steps, target systems, and compensation path;
- a reusable lesson field and audit identifier.

The reviewer can approve the recommendation, accept the bounded model proposal, edit the action and amount within the allowed schema, or reject it. Resume writes a correction ID, executes under a review-scoped idempotency key, verifies the result, and continues the original checkpoint.

## Reliability experiments

The workbench includes inspectable experiments for:

- **Memory ablation:** compare the same case with and without verified history.
- **Correction replay:** teach a bounded exception and observe a later comparable case change.
- **Retry safety:** submit one logical operation twice and verify one provider action.
- **Evidence faults:** corrupt a hash, expire a record, or mismatch a customer correlation.
- **Delayed outcomes:** attach a later failure and observe future reliability decrease.
- **Policy comparison:** evaluate the same packet under amount-first v4.9 and evidence-first v5.0.
- **Reliability envelope:** inspect the exact contexts that have earned each permission.
- **Evidence receipts:** view or download the canonical decision and its SHA-256 digest.

## Repository layout

```text
reliability-memory/
├── app/                         # React workbench, scenario data, and API client
├── aws-ui/                      # Static AWS application entry point
├── agent-skills/                # Inspectable capabilities composed inside the node
├── services/api/app/
│   ├── graph_runtime.py         # One-node LangGraph and durable interrupt/resume
│   ├── runtime.py               # End-to-end agent pipeline
│   ├── resolution_evidence.py   # Source admission and issue evidence
│   ├── resolution_selector.py   # Deterministic remedy selection
│   ├── policy.py                # Permission boundary
│   ├── repository.py            # CockroachDB persistence and vector retrieval
│   ├── mcp_memory.py            # Managed MCP independent verification
│   ├── workflows.py             # Typed idempotent operations
│   └── main.py                  # FastAPI composition root and routes
├── services/api/tests/          # Runtime, graph, policy, memory, and safety tests
├── db/migrations/               # Ordered CockroachDB schema and seed migrations
├── infra/aws/                   # AWS SAM infrastructure
├── scripts/                     # Migration, embedding, validation, and deployment tools
├── examples/                    # Example API request bodies
└── docs/                        # Product, architecture, operations, security, and walkthroughs
```

The dependency direction is intentional: domain types do not depend on infrastructure; evidence, policy, and workflow logic use repository and model adapters; `main.py` is the composition root that selects local or cloud implementations.

## Local setup

### Prerequisites

- Node.js 22.13 or newer
- Python 3.13
- Docker Desktop for local CockroachDB

### Install dependencies

```bash
git clone https://github.com/Iamns45/reliability-memory.git
cd reliability-memory

npm ci
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r services/api/requirements-dev.txt
```

### Run the complete local application

Start CockroachDB, apply migrations, seed the case catalog, and run the API:

```bash
docker compose up --build
```

In a second terminal, start the React application:

```bash
npm run dev
```

Open:

- Application: `http://localhost:3000`
- API documentation: `http://localhost:8000/docs`
- CockroachDB console: `http://localhost:8080`

The local API uses deterministic provider and model adapters unless cloud configuration is supplied. The selection, policy, workflow events, interrupt/resume, idempotency, persistence, and verification logic remain the same.

### Run a case through the streaming API

```bash
curl -N -X POST http://localhost:8000/v1/cases/stream \
  -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: early-failure-0001' \
  --data @examples/run-case.json
```

When `case_id` is present, the backend reloads the authoritative case and evidence bundle. Browser-supplied copies of amount, task, contract, and risk fields cannot replace stored facts.

## CockroachDB Cloud data preparation

Copy the required variable names from [.env.example](./.env.example) into the shell. Do not commit connection strings or service-account keys.

```bash
export DATABASE_URL='postgresql://USER:PASSWORD@HOST:26257/reliability_memory?sslmode=verify-full'
python scripts/migrate_and_seed.py --episodes 5000
python scripts/reindex_embeddings.py
```

Verify the independent read-only MCP path:

```bash
export COCKROACH_MCP_CLUSTER_ID='your-cluster-id'
read -r -s 'COCKROACH_MCP_API_KEY?Paste the service-account API key: '
export COCKROACH_MCP_API_KEY
python scripts/verify_managed_mcp.py
```

The migration runner is idempotent, records checksums, rejects modified applied migrations, and safely baselines the known legacy schema when necessary.

## AWS deployment

Prerequisites are authenticated AWS CLI credentials, Docker, AWS SAM CLI, Bedrock model access, a CockroachDB Cloud connection URL, and a cluster-scoped Managed MCP service-account key.

```bash
export AWS_PROFILE=reliability-deploy
export AWS_DEPLOY_REGION=us-east-1
export DATABASE_URL='postgresql://USER:PASSWORD@HOST:26257/reliability_memory?sslmode=verify-full'
export COCKROACH_MCP_CLUSTER_ID='your-cluster-id'
read -r -s 'COCKROACH_MCP_API_KEY?Paste the service-account API key: '
export COCKROACH_MCP_API_KEY

./scripts/deploy_aws.sh
```

The deployment script stores secrets, validates and prepares CockroachDB, re-indexes memory with Titan embeddings, builds the Lambda image and React assets, deploys the SAM stack, uploads the UI, invalidates CloudFront, and verifies the public health endpoint.

See [AWS deployment](./docs/operations/AWS_DEPLOYMENT.md) and the [operations runbook](./docs/operations/RUNBOOK.md) for configuration, rollback, and diagnosis.

## Quality and security

```bash
source .venv/bin/activate
npm run check
npm run audit:prod
```

The quality gate runs formatting, documentation validation, ESLint, CloudFormation validation, shell syntax checks, mypy, TypeScript checks, a production UI build, and 80 backend tests.

Important invariants include:

- CockroachDB transactions retry the complete operation on SQLSTATE `40001`.
- SQLSTATE `40003` is reconciled by idempotency key before replay.
- External actions remain outside database transactions.
- Pending and self-reported outcomes never increase reliability.
- Human corrections are lessons and overrides, not automatic successes.
- Safety and identity boundaries cannot be overridden by model confidence or similarity.
- Every bundled person, order, case, and episode is synthetic.

See [SECURITY.md](./SECURITY.md), the [threat model](./docs/security/THREAT_MODEL.md), and [CONTRIBUTING.md](./CONTRIBUTING.md).

## Current integration boundary

Payment, carrier, warranty, identity, safety, and infrastructure providers are represented by deterministic idempotent adapters. They produce real application events, retries, receipts, persistence, and verification without mutating external provider accounts. Replacing one with a production connector does not change the evidence, permission, checkpoint, or idempotency contracts.

The included case catalog and history are synthetic. Production use would require governed source connectors, organization-specific policies, calibrated outcome verification, access controls, and operational review of every autonomy context.

## License

MIT License — Copyright (c) 2026 Narne Srinivas. See [LICENSE](./LICENSE).
