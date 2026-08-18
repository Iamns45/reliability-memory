# ADR 0009: Managed MCP is an independent read-only memory proof

> Status: Accepted
>
> Date: 2026-08-17

## Context

The runtime already uses CockroachDB transactions for durable state and distributed vector queries for task-scoped experience. Autonomous execution also needs a visibly independent way to prove that the authorization record actually committed and that semantic retrieval agrees with the operational path. Using the same connection and code path for both the decision and its proof would make a shared defect harder to detect.

Managed MCP can expose CockroachDB reads through a separately authenticated, cluster-scoped protocol. It should not replace direct transactional SQL: idempotency, authorization, outcome, and LangGraph checkpoint writes have atomicity and retry requirements that belong in the repository adapter.

## Decision

After `create_decision_record()` commits and before an automatic workflow begins, the one LangGraph node will:

1. connect to CockroachDB Cloud Managed MCP with a service-account key held in AWS Secrets Manager;
2. set the cluster-scope header and discover the live `select_query` input schema;
3. read the exact episode ID, effective decision, and policy version;
4. run a task-scoped vector-neighbor query from the persisted embedding;
5. compare the MCP result with the direct distributed-vector retrieval;
6. hash and persist a typed verification receipt; and
7. contract `AUTO` or executable `DENY` to `HUMAN` when the required proof fails.

The MCP adapter accepts only statements beginning with `SELECT` or `WITH`. It has no write operation in its application contract. Direct SQL remains the only database write path.

## Consequences

- The two CockroachDB capabilities participate in each memory-enabled autonomous candidate.
- Every autonomous demo can show an episode ID, observed policy, vector overlap, MCP tool, cluster scope, and receipt hash.
- A Managed MCP outage fails safely to the existing prefilled review workflow instead of losing the case investigation.
- One run adds one MCP session and up to two bounded read queries before execution.
- Local deterministic mode stays usable, but clearly marks MCP as disabled and never presents a managed proof.
