# Testing strategy

> Status: Current
>
> Audience: Software engineers and reviewers
>
> Owner: Reliability Memory quality maintainers
>
> Last reviewed: 2026-08-16

## Quality objectives

Tests prioritize authorization invariants, scenario-specific evidence, transaction safety, durable review behavior, server-authoritative data, and honest UI/API integration. Rendering a convincing screen is insufficient; unsafe or incomplete inputs must be unable to cross the policy boundary.

## Test layers

| Layer                     | Location                                                                                                               | Primary coverage                                                                                              |
| ------------------------- | ---------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| Evidence and policy units | `services/api/tests/test_case_catalog.py`, `test_payment_evidence.py`, `test_reliability.py`, `test_counterfactual.py` | issue diversity, source contracts, economics, scoring, permission invariants, and validated permission deltas |
| Runtime                   | `services/api/tests/test_runtime.py`                                                                                   | decision persistence, workflow plan, step receipts, verification, correction immutability, and idempotency    |
| Graph                     | `services/api/tests/test_graph_runtime.py`                                                                             | one-node topology, typed state, workflow events, interrupt/resume execution, replay, and experiments          |
| API                       | `services/api/tests/test_api.py`, `test_configuration.py`                                                              | validation, health, SSE, catalog authority, and adapter selection                                             |
| Catalog acceptance        | `services/api/tests/test_case_catalog.py`                                                                              | all 26 cases match permission, provenance, required sources, alternatives, and containment inputs             |
| Web artifact              | `tests/*.test.mjs`                                                                                                     | server rendering, runtime client wiring, and self-contained AWS output                                        |
| Static analysis           | repository configuration                                                                                               | ESLint, TypeScript, mypy, Black, Prettier, CloudFormation, shell syntax, and docs links                       |

## Required commands

```bash
npm run check
npm run audit:prod
```

`npm run check` runs formatting verification, documentation validation, linting, infrastructure checks, Python typing, TypeScript typing, builds, and automated tests.

## Critical acceptance scenarios

1. Every catalog task exposes a non-empty, task-matching evidence bundle.
2. Missing required evidence prevents automatic execution.
3. A proposal that differs from the evidence-derived action or value is denied or sent to human review according to its hard floor.
4. Early product failure can replace from an unaffected batch only after diagnostics, warranty, quality, and inventory facts agree.
5. Cosmetic damage remains `VERIFY` because the customer must choose a keep-item offer.
6. A safety incident remains `HUMAN` regardless of amount or historical reliability.
7. Identity mismatch remains `DENY` with a documented appeal path.
8. High-value freight exposure remains `HUMAN` even with strong current evidence.
9. A repeated idempotency key maps to one episode and one provider action.
10. A supervised graph pauses with a complete workflow summary, then resumes with a correction ID, step receipts, and independent verification.
11. A verified warranty-grace correction changes a later comparable proposal but does not instantly grant `AUTO`.
12. Removing memory removes earned permission; a delayed adverse outcome reduces future reliability.
13. A catalog ID overrides altered browser facts.
14. Compatibility tests preserve exact payment proof for future payment-related integrations.
15. A retry reuses the workflow and provider references rather than repeating an operation.
16. A stale record, altered source payload, or mismatched customer correlation produces `BLOCKED` evidence and cannot auto-execute.
17. Every completed automatic workflow returns a verified containment proof with exact evidence record IDs.
18. A reported counterfactual is accepted only when replaying its typed changes through policy v5.0 produces the stated mode.
19. Explicit safety, denial, human, and customer-confirmation floors remain hard boundaries in the counterfactual output.
20. Evidence-fault controls downgrade integrity, freshness, or correlation without persisting a decision or executing a workflow.
21. Every autonomy-register entry points to the prior entry hash and the published head matches the final record.

## Test data rules

- Use deterministic synthetic records.
- Use Srinivas only for the designated customer demonstration and realistic fictional names elsewhere.
- Never add secrets, live provider references, real payment tokens, or real customer data.
- Keep expected permission beside each case and assert the complete catalog.
- A customer claim-rate field may affect review but cannot alone drive `DENY`.

## Change-to-test matrix

| Changed area           | Minimum evidence                                                                                 |
| ---------------------- | ------------------------------------------------------------------------------------------------ |
| Evidence evaluator     | Complete packet, missing source, mismatched issue, and invalid economics tests                   |
| Policy or reliability  | Boundary unit tests plus runtime or catalog assertion                                            |
| New issue type         | At least one full catalog case, required sources, options, expected permission, and UI rendering |
| Graph state or review  | Interrupt/resume test and API contract update                                                    |
| Endpoint or event      | API integration test and API document update                                                     |
| Repository transaction | Idempotency/retry test and data-model update                                                     |
| Migration              | Retry-safe review and local or cloud validation                                                  |
| UI result mapping      | Rendered test and runtime-response assertion                                                     |
| AWS template or script | `cfn-lint`, shell syntax, build, and smoke check when credentials exist                          |
| Documentation          | `npm run lint:docs`                                                                              |

## Exit criteria

A change is ready when the full gate passes, critical behavior has direct automated evidence, documentation matches implementation, and cloud-only validation not executed in the current environment is explicitly identified.
