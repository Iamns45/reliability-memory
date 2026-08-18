# ADR 0006: Compile authorized actions into typed idempotent workflows

> Status: Accepted
>
> Audience: Backend, integration, frontend, and reliability engineers
>
> Owner: Reliability Memory maintainers
>
> Last reviewed: 2026-08-16

## Context

A permission decision is not a customer resolution by itself. A replacement, refund, warranty repair, safety escalation, and seller investigation affect different systems and require different rollback or escalation behavior. A single generic provider receipt hides operational work and makes human approval ambiguous.

## Decision

The agent compiles every proposal into a typed `WorkflowPlan` before permission can produce a side effect. The plan declares the objective, ordered operations, target systems, reversibility, and compensation rule. Automatic permission executes immediately. `VERIFY` and `HUMAN` pause with the same plan, then execute a plan rebuilt from the reviewer-approved action on resume.

The executor emits start and completion events for the workflow and each operation. It returns one stable workflow ID, one stable action ID, step-level provider references, and named artifacts. The entire workflow uses one logical idempotency key; reviewed execution uses `review:{episode_id}`.

## Consequences

- The UI can show exactly what will happen before approval and what happened afterward.
- Evidence receipts include downstream operation references, not only the monetary amount.
- A repeated logical request cannot create a second workflow in the current executor.
- Human approval resumes useful work instead of merely recording a correction.
- Provider integrations must preserve the same operation, event, idempotency, and compensation contract.
- The demo adapter returns deterministic provider receipts; replacing it with production provider APIs does not change policy or graph topology.

## Verification

Runtime, graph, and API tests assert the plan, step count, artifacts, streamed workflow events, human-approved execution, correction ID, verification result, and repeated-request behavior.
