# Reliability Memory

> Resolution agents should earn narrow autonomy from verified outcomes.

- **Live application:** [https://d30n5k4sgmvobz.cloudfront.net/](https://d30n5k4sgmvobz.cloudfront.net/)
- **Runtime health:** [https://d30n5k4sgmvobz.cloudfront.net/health](https://d30n5k4sgmvobz.cloudfront.net/health)

Reliability Memory is an evidence-driven consumer-resolution workbench. One typed LangGraph node investigates damage, delivery, warranty, safety, identity, and product-quality cases; retrieves verified experience; computes the best eligible remedy; asks Amazon Bedrock for a bounded proposal; applies deterministic policy; executes only authorized workflows; verifies containment; and records the result in CockroachDB. The enterprise incident cases demonstrate that the same reliability engine generalizes without adding domain-specific graph branches.

The language model never chooses the preferred remedy or `AUTO`, `VERIFY`, `HUMAN`, or `DENY`. A deterministic selector calculates the remedy from eligible options, goal fit, customer-value components, company cost, and case limits. Permission then comes from current evidence, issue-specific rules, safety boundaries, and independently verified history.

## What the judge can do

The analyst queue contains 26 synthetic, database-backed cases rather than one repeated claim pattern. Eighteen consumer cases cover product, delivery, safety, identity, warranty, and payment-adjacent operations. Eight enterprise cases cover cost anomalies, failed deployments, access recovery, database capacity, traffic stabilization, credential containment, isolated restore, and quota changes.

Examples include:

- cosmetic damage where Srinivas can choose a keep-item discount plus warranty;
- an early-life blender failure linked to a bad manufacturing batch;
- a missing delivery with an off-location carrier scan;
- a missing laptop charger proven by package weight and bill of materials;
- the wrong product variant proven by order and warehouse barcodes;
- high-value freight damage that requires supervisor approval;
- a smoke report that always routes to the safety team;
- porch theft with conflicting evidence and a neutral human review;
- a serial-number mismatch that is denied with an appeal path;
- a warranty-grace exception whose correction changes a later comparable case;
- partial shipments, firmware recovery, late-delivery recovery, counterfeit risk, and product-quality-driven retention offers.
- a failed deployment that safely rolls back to a signed, schema-compatible release;
- read-capacity exhaustion that adds an expiring replica only after alternate causes are excluded;
- a retry storm contained through a load-tested backoff policy instead of an unnecessary quota increase;
- privileged credential containment and isolated data restore that remain human-owned despite exact evidence.

Every case file shows the customer goal, company guardrail, authoritative evidence sources, source record IDs, authority, integrity, freshness, entity correlation, conflict status, alternative resolutions, value components, goal fit, selection formula, customer value, company cost, model proposal, deterministic permission, streamed trace, containment proof, and persisted audit IDs. The interface renders the runtime response; preview records are used only when an API is not configured and are labeled accordingly.

External provider operations are simulated by deterministic idempotent adapters. They produce real workflow events, persistence, retry behavior, receipts, and verification inside this system, but they do not call real payment, carrier, warranty, identity, or infrastructure accounts.

The resulting action is a typed workflow rather than a single generic receipt. Depending on the issue, it can reserve inventory, create a shipment or repair authorization, issue a payment adjustment, open a quality or safety incident, update the case ledger, and notify the customer. Every operation emits a backend event and returns its own idempotent provider reference.

The reliability lab demonstrates memory ablation, correction replay, a downloadable evidence receipt, retry-safety failure injection, live hash/freshness/correlation faults, the earned reliability envelope, a hash-chained autonomy register, delayed adverse outcomes, and policy-version comparison. Every run also includes a policy-validated counterfactual that states the smallest evidence, outcome, or cost change that would reach `AUTO`, or identifies the hard boundary that makes `AUTO` intentionally unavailable.

## Judge guide

Start with `CASE-202-26`, **Blender motor failed after two days**. Its serial-linked diagnostics, warranty record, defective-batch rate, replacement inventory, and resolution economics are loaded from CockroachDB. The run retrieves task-scoped vector memory, produces a bounded Bedrock proposal, passes deterministic policy, obtains an independent Managed MCP database proof, executes the typed replacement workflow, verifies containment, and displays the persisted episode ID and receipt.

Two CockroachDB challenge tools are part of the working runtime:

| Tool                                    | Meaningful use in this project                                                                                                                                                                                                         |
| --------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| CockroachDB Distributed Vector Indexing | Stores normalized 1,024-dimensional Titan embeddings beside operational episode data. Task-prefixed vector indexes retrieve verified comparable outcomes and corrections without a separate vector service.                            |
| CockroachDB Cloud Managed MCP Server    | Lambda calls the read-only `select_query` tool before an autonomous action. It independently reloads the persisted decision and repeats the vector-neighbor query; a missing or mismatched proof contracts permission to human review. |

AWS provides the public execution environment:

| Service                | Responsibility                                                                                            |
| ---------------------- | --------------------------------------------------------------------------------------------------------- |
| Amazon Bedrock         | Nova Lite produces bounded action proposals; Titan Text Embeddings V2 creates memory vectors.             |
| AWS Lambda             | Runs FastAPI, the one-node LangGraph, deterministic policy, workflow adapters, and outcome verification.  |
| Amazon API Gateway     | Exposes the HTTP and streamed SSE API with throttling and access logs.                                    |
| Amazon S3 + CloudFront | Hosts the private static UI origin and serves the public HTTPS judge application.                         |
| AWS Secrets Manager    | Holds the CockroachDB connection URL and Managed MCP service-account key outside source and browser code. |
| Amazon CloudWatch      | Retains Lambda and API operational logs.                                                                  |

For a guided evaluation, follow the [2:58 demo script](./docs/submission/DEMO_SCRIPT.md) and the [submission narrative](./docs/submission/DEVPOST_SUBMISSION.md).

## Decision model

```mermaid
flowchart LR
    C["Customer case"] --> G["One typed LangGraph node"]
    G --> F["Authoritative facts"]
    F --> E["Issue-specific evidence packet"]
    E --> M["Verified experience from CockroachDB"]
    M --> B["Bedrock Nova Lite proposal"]
    B --> P["Deterministic policy v5.0"]
    P -->|"candidate AUTO / executable DENY"| MCP["Managed MCP read-only proof"]
    MCP -->|"episode + vector memory match"| X["Idempotent multi-step workflow"]
    MCP -->|"required proof fails"| H
    P -->|"VERIFY / HUMAN"| H["Prefilled human review"]
    P -->|"DENY with exact proof"| D["Execute denial + appeal workflow"]
    X --> V["Independent outcome verification"]
    H -->|"approve + resume same checkpoint"| X
    V --> R[("CockroachDB episode + receipt")]
    G --> R
```

The current policy evaluates in this order:

1. Reject invalid values and unsupported actions.
2. Respect abuse, safety, high-value, identity, and eligibility boundaries.
3. Admit every required source only when its authority, record provenance, SHA-256 integrity, freshness window, case/customer/task correlation, and conflict metadata pass.
4. Reject ineligible or over-limit remedies and select the highest goal-adjusted customer value per company dollar.
5. Require the proposal to match the computed action and bounded value.
6. Enforce customer-choice, human-approval, and delegated company-cost limits.
7. Use verified comparable outcomes only after current-case eligibility succeeds.
8. Execute `AUTO` and exact evidence-backed denials immediately; pause supervised decisions with a prefilled workflow and execute only after explicit approval.
9. Re-evaluate a copied input packet to prove which minimal changes would reach `AUTO`; never suggest that history can override a hard floor.
10. Emit a containment proof tying the root cause, admitted record IDs, policy rule, workflow ID, operations, verification, economics, and reopen monitor together.

This means “under $100” is never sufficient by itself. A $29 part shipment can execute when package-weight and bill-of-material evidence agree; a $25 retention offer can still require review; and a safety report remains human-controlled regardless of amount or historical success.

## Runtime architecture

- **Agent graph:** LangGraph with exactly one executable node and `AgentGraphState` typed state. `START` and `END` are framework sentinels, not business nodes.
- **Proposal model:** Amazon Bedrock Converse using `amazon.nova-lite-v1:0`.
- **Memory embedding:** Amazon Titan Text Embeddings V2 with normalized 1,024-dimensional vectors.
- **System of record:** CockroachDB Cloud for cases, evidence bundles, entities, episodes, outcomes, corrections, policies, approvals, audits, vectors, and durable LangGraph checkpoints through `CockroachDBSaver`.
- **Independent memory proof:** CockroachDB Cloud Managed MCP uses a cluster-scoped service account and the read-only `select_query` tool to verify the persisted episode and replay the vector-neighbor query before autonomous execution.
- **Judge UI:** React static assets in a private S3 origin behind public CloudFront HTTPS.
- **API:** FastAPI/Mangum container on Lambda behind API Gateway.

See the [system design](./docs/architecture/SYSTEM_DESIGN.md), [API contract](./docs/architecture/API_CONTRACT.md), and [data model](./docs/architecture/DATA_MODEL.md).

## Repository map

```text
app/                         Analyst workbench and reliability lab
agent-skills/                Five capabilities used inside the single node
services/api/app/            API, graph, evidence, memory, policy, and adapters
services/api/tests/          Unit, graph, stream, replay, and safety tests
db/migrations/               Ordered CockroachDB schema and seed migrations
infra/aws/                   AWS SAM infrastructure
scripts/                     Migration, seed, validation, and deployment tooling
docs/product/                Requirements and shared terminology
docs/architecture/           System, API, data, and decision records
docs/development/            Local setup, testing, and code walkthrough
docs/operations/             Deployment and runbook
docs/security/               Threat model
docs/submission/             Judge demo and submission narrative
```

The documentation index is [docs/README.md](./docs/README.md).

## Local development

Requires Node.js 22.13+ and Python 3.13.

```bash
npm ci
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r services/api/requirements-dev.txt
npm run dev
```

Open `http://localhost:3000`. To run CockroachDB and the API locally:

```bash
docker compose up --build
```

Useful endpoints:

- Dashboard: `http://localhost:3000`
- API: `http://localhost:8000`
- API schema: `http://localhost:8000/docs`
- CockroachDB console: `http://localhost:8080`

Run the early-failure catalog case:

```bash
curl -N -X POST http://localhost:8000/v1/cases/stream \
  -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: early-failure-0001' \
  -d '{
    "case_id": "CASE-202-26",
    "customer_id": "C-202",
    "request_text": "Run the authoritative catalog case.",
    "requested_amount": 89,
    "memory_enabled": true
  }'
```

When `case_id` is present, the server reloads the authoritative case and evidence bundle. Browser-supplied task, amount, contract, and risk values cannot overwrite those stored facts.

## Human review

A `VERIFY` or `HUMAN` decision interrupts the same durable graph thread. The review packet already contains:

- the customer request and goal;
- current proposal and policy reasons;
- every completed or blocking evidence source;
- recommended action, amount, customer value, and company cost;
- alternatives, reusable lesson, nearest episode IDs, and audit ID.
- the exact workflow steps, target systems, compensation path, and pending side effects.

The reviewer can confirm the suggestion, accept the proposal, edit the bounded resolution, or reject it. Resuming persists a correction ID, executes the approved workflow with a review-scoped idempotency key, verifies the result, and continues the original checkpoint; the analyst does not rebuild the investigation.

## CockroachDB Cloud seed

Apply every numbered migration and seed the case catalog plus verified episodes:

```bash
python scripts/migrate_and_seed.py --episodes 5000
```

The catalog seed is idempotent and writes the issue-specific JSON evidence bundles used by the runtime and UI. The episode seed spans every case task and action so reliability is contextual rather than global.

The default local run needs no credentials. When connecting cloud dependencies, copy the required names from [.env.example](./.env.example) into your shell environment. Production credentials must remain in the shell or AWS Secrets Manager and must never be committed. Request examples are available under [examples](./examples/).

## AWS deployment

Prerequisites are valid AWS credentials, Docker, SAM CLI, a CockroachDB Cloud connection URL, a cluster-scoped Managed MCP service-account key, and Bedrock model access in the selected region.

```bash
export DATABASE_URL='postgresql://reliability_runtime:...@.../reliability_memory?sslmode=verify-full'
export COCKROACH_MCP_CLUSTER_ID='your-cluster-id'
read -r -s 'COCKROACH_MCP_API_KEY?Paste the service-account API key: '
export COCKROACH_MCP_API_KEY
./scripts/deploy_aws.sh
```

The deployment script validates prerequisites, stores the database secret, migrates and seeds CockroachDB, builds the Lambda container and UI, deploys API Gateway/S3/CloudFront, invalidates the CDN, verifies `/health`, and prints the public judge URL. Judges need no AWS account or sign-in.

See [AWS deployment](./docs/operations/AWS_DEPLOYMENT.md) and the [operations runbook](./docs/operations/RUNBOOK.md).

## Quality gate

```bash
npm run check
npm run audit:prod
```

The suite verifies the one-node graph, typed state, real SSE ordering, interrupt/resume with approved execution, issue-specific workflow plans, step receipts, correction persistence and replay, catalog authority, strict evidence admission, tamper/staleness/correlation failures, policy-validated counterfactuals, autonomy-ledger hash continuity, impact aggregation, containment proof, action/economics invariants, safety escalation, memory ablation, delayed outcomes, policy comparison, receipt integrity, and retry-safe execution.

## Production invariants

- CockroachDB writes use short transactions with full-transaction retries for SQLSTATE `40001`.
- SQLSTATE `40003` is reconciled by idempotency key before any provider replay.
- External actions remain outside database transactions.
- AWS autonomy requires a read-only Managed MCP receipt that matches the persisted episode, permission, policy version, and direct vector-memory result.
- Pending and self-reported results never improve reliability.
- Human corrections count as overrides and reusable lessons, not automatic successes.
- A customer's claim frequency is one review signal, never proof of wrongdoing.
- Product safety and identity conflicts cannot be overridden by similarity or model confidence.
- Every bundled person, order, and episode is synthetic.

See [CONTRIBUTING.md](./CONTRIBUTING.md) for engineering standards.

## Submission assets

- [Three-minute demo script](./docs/submission/DEMO_SCRIPT.md)
- [Submission copy](./docs/submission/DEVPOST_SUBMISSION.md)
- [System design](./docs/architecture/SYSTEM_DESIGN.md)
- [Threat model](./docs/security/THREAT_MODEL.md)

## License

[MIT](./LICENSE)
