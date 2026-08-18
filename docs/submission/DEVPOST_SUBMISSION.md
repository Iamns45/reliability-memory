# Devpost submission copy

> Status: Current
>
> Audience: Hackathon submission reviewers
>
> Owner: Reliability Memory submission maintainers
>
> Last reviewed: 2026-08-16

Engineering behavior is defined by the [product requirements](../product/PRODUCT_REQUIREMENTS.md), [system design](../architecture/SYSTEM_DESIGN.md), and [API contract](../architecture/API_CONTRACT.md).

## Project name

Reliability Memory

## Tagline

Agents should earn narrow autonomy from verified experience.

## Inspiration

Consumer-resolution automation often uses the same amount threshold and history checklist for damage, delivery, warranty, safety, and identity problems. That misses the operational question: what records prove this specific issue, which eligible remedy best serves the customer without unnecessary company loss, and has the agent succeeded in comparable contexts before?

## What it does

Reliability Memory is a consumer-resolution analyst workbench and runtime. One typed LangGraph node loads authoritative facts, validates provenance and integrity, builds a task-specific evidence packet, computes the best eligible remedy, retrieves verified organizational experience, asks Amazon Bedrock for a bounded proposal, applies deterministic policy, executes only authorized workflows, independently verifies containment, and writes the resulting memory to CockroachDB.

The primary product contains eighteen consumer cases covering damage, delivery, early device failure, freight, variants, components, safety, identity, authenticity, warranty, partial shipment, remote recovery, and quality-aware retention. Eight enterprise incident cases are included as a generalization proof: the same reliability engine, policy boundary, memory model, and one-node graph handle deployment, access, capacity, traffic, security, restore, and quota workflows without domain-specific graph branches.

Each case shows the goal, company guardrail, source-level facts, authority, record ID, integrity, freshness, entity correlation, conflicts, alternatives, customer value, company cost, real backend events, deterministic permission, containment proof, and persisted episode/correction IDs. `case_id` makes repository facts authoritative; browser changes cannot alter policy inputs.

Srinivas's working but dented espresso machine demonstrates the balance. The product has elevated transit returns. The runtime—not a seeded recommendation—compares three eligible remedies. It derives $95 customer value from a $60 immediate adjustment plus $35 expected two-year warranty coverage, applies the option's goal fit, and selects the highest goal-adjusted value per company dollar. Policy still returns `VERIFY` because customer choice is mandatory. A blender that fails on day two takes a different path: device telemetry, warranty, bad-batch data, and unaffected inventory support automatic replacement. A smoke report always routes to human safety review. A missing laptop charger results in a component shipment rather than replacing a $1,299 bundle.

Provider execution is deliberately scoped: payment, carrier, warranty, identity, and infrastructure calls are simulated by deterministic idempotent adapters. The streamed workflow, persistence, retries, receipts, verification, interrupts, corrections, and policy decisions are real application behavior, but no external provider account is mutated.

## How we built it

- Exactly one executable LangGraph node with `AgentGraphState`, real SSE events, and durable interrupt/resume.
- Amazon Bedrock Converse with Nova Lite for proposals only.
- Amazon Titan Text Embeddings V2 for normalized 1,024-dimensional task-scoped memory vectors.
- CockroachDB for customer/case facts, JSON evidence bundles, policies, episodes, actions, outcomes, corrections, approvals, audits, vectors, and LangGraph checkpoints.
- Deterministic policy v5.0 outside the model, with issue source completeness, action/value agreement, safety and identity boundaries, customer-choice floors, cost caps, and verified reliability.
- Strict evidence grades: `EXACT`, `REVIEW`, and `BLOCKED`, based on authority, provenance, SHA-256 integrity, freshness, exact correlation, uniqueness, and conflict checks.
- Deterministic runtime resolution selection from eligible options, reconciled customer-value components, goal fit, company cost, and case limits; no preferred remedy is stored in the case bundle.
- Typed containment proof linking admitted record IDs to root cause, policy rule, workflow receipt, verification, economics, and reopen monitoring.
- FastAPI on Lambda/API Gateway plus a React workbench from private S3 through public CloudFront.

## CockroachDB capabilities

Task-prefixed distributed vector indexes retrieve comparable verified episodes and human lessons without mixing unrelated tasks. Exact SQL simultaneously supplies current case facts, source evidence, outcome aggregates, policy versions, and audit state. The same database transactionally preserves the proposal, authorization, outcome, correction, and checkpoint, eliminating synchronization with a separate vector service.

Before an autonomous workflow executes, the Lambda runtime also uses the CockroachDB Cloud Managed MCP Server's read-only `select_query` tool. It reloads the persisted episode and repeats the task-scoped vector-neighbor query through an independent, cluster-scoped path. The proof must match the direct database result, policy version, permission, and episode; otherwise the runtime contracts the decision to human review. The MCP credential remains in AWS Secrets Manager and is never sent to the browser.

Transaction design uses randomized UUIDs, short writes, parameterized SQL, complete-operation retry on `40001`, reconciliation of ambiguous commits, unique idempotency keys, and external actions outside database transactions.

## Reliability demonstrations

- **Memory ablation:** the same case with and without verified history.
- **Correction replay:** a human-taught 14-day warranty-grace repair changes a later case.
- **Evidence receipt:** visible/downloadable canonical record with SHA-256 digest.
- **Retry safety:** the repeated request returns one episode and one provider action.
- **Reliability envelope:** exact contexts that have earned each permission.
- **Delayed outcome:** a later adverse result lowers future reliability.
- **Policy comparison:** weak amount-first v4.9 beside evidence-first v5.0.
- **Policy-validated counterfactual:** the smallest evidence, outcome, or cost delta that actually flips v5.0 to `AUTO`, or the hard boundary that prevents it.
- **Evidence fault lab:** judges can corrupt a hash byte, expire a source, or mismatch a customer correlation and watch `EXACT` contract to `BLOCKED` without executing a side effect.
- **Impact and authority records:** verified outcome economics versus a refund-first baseline plus a dated, hash-chained autonomy register.

## Challenges

The hardest problem was preventing similarity from becoming proof. We separated current issue evidence, proposal, permission, execution, and verification. Required sources vary by task; pending and self-reported results never increase reliability; human corrections count as overrides and lessons; and safety, identity, high-impact, and customer-choice boundaries remain deterministic.

We also had to make the human handoff useful. The graph now pauses only after assembling the request, evidence, alternatives, economics, model proposal, policy rationale, suggested action, and lesson. The analyst confirms or edits the summary and resumes the same checkpoint.

## Accomplishments

- 18 scenario-specific consumer case files, plus 8 enterprise cases proving the same reliability engine generalizes without a second product-specific graph.
- The model cannot grant itself permission or bypass evidence, safety, identity, cost, or customer-choice rules.
- Product reviews, return rates, device diagnostics, batch quality, carrier evidence, warehouse records, and customer history produce different actions by problem.
- Real stream, CockroachDB-backed LangGraph checkpoint, correction replay, episode IDs, correction IDs, receipts, retry proof, and policy-validated counterfactuals.
- Automated coverage for the one-node graph, catalog authority, tamper/staleness/correlation blocking, containment proof, permission matrix, streaming, interrupt/resume, verification, delayed outcomes, and idempotency.

## What we learned

Memory becomes operationally important when it changes what an agent is allowed to do. Better customer outcomes do not require ignoring company economics: the useful unit is a verified, issue-specific resolution option with explicit customer value, company cost, and a deterministic boundary.

## Next

Add live carrier, order-management, device-telemetry, warranty, inventory, product-quality, and safety integrations; version evidence schemas; add cohort-safe systemic issue detection; and continuously ingest delayed recovery and satisfaction outcomes.

## CockroachDB tools used

- **CockroachDB Distributed Vector Indexing:** task-scoped semantic retrieval over verified episodes and human corrections.
- **CockroachDB Cloud Managed MCP Server:** independent read-only persistence and vector-memory proof before autonomous execution.

## AWS services used

- **Amazon Bedrock:** Nova Lite bounded proposals and Titan Text Embeddings V2 memory vectors.
- **AWS Lambda:** FastAPI, LangGraph, evidence evaluation, policy, execution, and verification.
- **Amazon API Gateway:** public HTTP and SSE API.
- **Amazon S3 and CloudFront:** private static origin and public HTTPS judge UI.
- **AWS Secrets Manager:** database and Managed MCP credentials.
- **Amazon CloudWatch:** runtime and API logs.

## Built with

CockroachDB Cloud, CockroachDB Distributed Vector Indexing, CockroachDB Cloud Managed MCP Server, LangGraph, Amazon Bedrock, Amazon Titan Text Embeddings V2, Amazon Nova Lite, AWS Lambda, API Gateway, AWS Secrets Manager, Amazon S3, Amazon CloudFront, CloudWatch, FastAPI, Python, React, and TypeScript.
