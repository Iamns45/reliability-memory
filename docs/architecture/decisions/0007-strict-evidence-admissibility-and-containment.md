# ADR 0007: Admit exact evidence and emit containment proof

> Status: Accepted
>
> Audience: Backend, policy, data, security, frontend, and reliability engineers
>
> Owner: Reliability Memory maintainers
>
> Last reviewed: 2026-08-16

## Context

Source presence is not proof. A record can be stale, altered, produced by an untrusted system, attached to the wrong customer, duplicated, or contradicted by another record. Labeling every present source “verified” would make automatic execution depend on an assertion rather than an enforceable contract. A successful provider call also does not prove the full case was contained.

## Decision

Each case defines an evidence snapshot time and a required source key set. Every source declares authority, source system, immutable record ID, payload digest, observation time, maximum age, exact case/customer/task correlation, and conflicts. The runtime independently validates all fields and recomputes the SHA-256 digest.

Evidence receives one of three grades:

- `EXACT`: every required record passes admission and no record carries a warning;
- `REVIEW`: every required record is admissible, but at least one warning requires confirmation;
- `BLOCKED`: a required record is missing or fails authority, provenance, integrity, freshness, correlation, uniqueness, or conflict checks.

Only `EXACT` can support automatic execution. `REVIEW` can support a prefilled supervised plan. `BLOCKED` cannot cross the execution boundary.

Every run also returns a typed `ContainmentProof`. Before execution it records the intended autonomy level and exact evidence IDs. After execution it adds containment status, workflow ID, operation count, independent verification, value economics, estimated human time avoided, and a seven-day reopen monitor. The proof is persisted in the episode/audit record and rendered directly by the UI.

## Consequences

- A browser or model cannot convert source presence into permission.
- A modified summary fails integrity even when every other field is unchanged.
- Stale or miscorrelated records cannot satisfy a required source key.
- Warning evidence remains useful without being mislabeled as autonomous proof.
- Analysts and judges can trace a decision from exact records through policy and execution to verification.
- Provider adapters must preserve record provenance and containment receipt semantics.

## Verification

Evidence unit tests alter payloads, timestamps, and customer correlation and assert grade `BLOCKED`. Catalog acceptance verifies provenance for all 26 cases. API tests assert the admissibility event and a verified containment result. Type, formatting, lint, graph, runtime, web, and infrastructure checks run together under `npm run check`.
