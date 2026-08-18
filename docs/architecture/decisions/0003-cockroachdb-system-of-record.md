# ADR 0003: Use CockroachDB as the system of record

> Status: Current (decision: Accepted)
>
> Audience: Architecture, data, and operations contributors
>
> Owner: Reliability Memory maintainers
>
> Last reviewed: 2026-08-16

## Context

The workflow needs authoritative entities and payments, transactional episode and outcome state, human corrections, audit history, vector retrieval, idempotency, and durable LangGraph checkpoints. Splitting these concerns across an operational database, vector store, and checkpoint service would create synchronization and provenance gaps.

## Decision

Store structured operational facts, `VECTOR(1024)` semantic memory, policy versions, approvals, audit events, and LangGraph checkpoints in CockroachDB. Use task-prefixed vector indexes for retrieval and serializable short transactions for state changes.

External provider calls stay outside database transactions. SQLSTATE `40001` retries the complete database operation; SQLSTATE `40003` triggers idempotency reconciliation before any provider replay.

## Consequences

- Structured facts and retrieved memories share one transactional provenance boundary.
- Evidence receipts can join all persisted decision records without an ETL pipeline.
- The runtime depends on careful idempotency and retry behavior under serializable isolation.
- Local tests use a behaviorally compatible in-memory repository, while cloud acceptance must also run against CockroachDB.

## Compliance evidence

Numbered migrations define objects and grants; repository tests cover episode creation, correction immutability, delayed outcomes, and duplicate-request behavior.
