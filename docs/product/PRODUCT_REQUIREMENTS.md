# Product requirements

> Status: Current
>
> Audience: Product owners, engineers, and judges
>
> Owner: Reliability Memory maintainers
>
> Last reviewed: 2026-08-16

## Problem statement

Consumer-resolution automation commonly applies one shallow threshold to damage, delivery, warranty, safety, and identity problems. That ignores the evidence needed for each issue, frustrates customers with repetitive investigation, and exposes the company to avoidable loss. Model confidence also does not prove that an action has worked safely in a comparable context.

Reliability Memory builds a case-specific evidence packet, computes the best eligible resolution from customer outcome and company economics, and uses verified outcomes to earn narrow autonomy. The model proposes; deterministic policy authorizes. Enterprise operations are a secondary generalization proof: the same engine and trust boundary also handle bounded incident-response workflows without domain-specific graph branches.

## Product principles

1. Customer satisfaction and loss prevention are simultaneous constraints, not opposing slogans.
2. Every issue type defines its own required sources and acceptable actions.
3. Past claim frequency informs review but never proves customer wrongdoing.
4. Product-wide defect and return signals can change the resolution plan.
5. Safety, identity, eligibility, and high-impact boundaries remain human-controlled.
6. A supervised analyst receives the completed investigation and edits only what needs judgment.
7. Memory affects permission only after outcomes are independently verified.
8. A source is usable only when authority, provenance, integrity, freshness, entity correlation, and conflicts are explicitly checked.
9. Every completed workflow emits a containment proof that can be audited independently of the UI.
10. The preferred resolution is computed at runtime from eligible options; it is never stored as the answer in the case bundle.

## Users

| User                       | Primary need                                                                                |
| -------------------------- | ------------------------------------------------------------------------------------------- |
| Resolution analyst         | Understand the customer, issue, facts, options, economics, and permission in one case file  |
| Human reviewer             | Confirm or edit a prefilled plan without repeating the investigation                        |
| Reliability owner          | Inspect where autonomy is earned and retract it after adverse outcomes                      |
| Quality or logistics owner | See systemic product, batch, seller, warehouse, and carrier signals exposed by cases        |
| Enterprise service owner   | Recover deployments, access, data, capacity, traffic, cost, and security with bounded plans |
| Hackathon judge            | Exercise real backend behavior and see persisted proof                                      |
| Operator                   | Deploy, monitor, diagnose, and recover the AWS and CockroachDB stack                        |

## Functional requirements

| ID    | Requirement                                                          | Acceptance evidence                                                                                                       |
| ----- | -------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| FR-01 | Execute through exactly one LangGraph business node with typed state | `/health` and the graph test report one executable node                                                                   |
| FR-02 | Stream actual backend stages                                         | SSE tests observe context, case evidence, memory, proposal, policy, action or review, and completion                      |
| FR-03 | Pause and resume the same durable thread                             | Review returns a prefilled summary; resume returns a persisted correction ID                                              |
| FR-04 | Render the runtime result                                            | UI proposal, permission, trace, evidence, and IDs come from the API response                                              |
| FR-05 | Keep UI and API permission identical                                 | The UI displays the exact response enum without client-side policy                                                        |
| FR-06 | Load authoritative cases from the repository                         | Catalog exposes 26 cases; `case_id` overrides altered browser copies                                                      |
| FR-07 | Use an evidence contract per issue type                              | Required sources differ for damage, delivery, failure, component, safety, seller, and identity cases                      |
| FR-08 | Evaluate more than refund amount                                     | Options show customer value, company cost, operational constraints, and the selected action                               |
| FR-09 | Use customer and product history responsibly                         | History and product quality appear as facts; frequency alone cannot deny a claim                                          |
| FR-10 | Persist every decision and accepted correction                       | Episode and correction IDs appear in results and receipts                                                                 |
| FR-11 | Make a repeated request safe                                         | Failure injection returns one episode and one provider reference                                                          |
| FR-12 | Demonstrate memory ablation                                          | With-memory and without-memory results expose reliability and permission deltas                                           |
| FR-13 | Replay a verified correction                                         | A warranty-grace lesson changes a later comparable proposal and permission                                                |
| FR-14 | Produce an evidence receipt                                          | Receipt contains the canonical persisted record and SHA-256 digest                                                        |
| FR-15 | Expose the reliability envelope                                      | API lists exact task, contract, evidence, cost, and permission contexts                                                   |
| FR-16 | React to delayed outcomes                                            | A later adverse result reduces future task reliability                                                                    |
| FR-17 | Compare policy versions                                              | The same packet shows amount-first v4.9 beside evidence-first v5.0                                                        |
| FR-18 | Support public AWS judge access                                      | CloudFront serves the UI and routes the API to Lambda/API Gateway                                                         |
| FR-19 | Seed CockroachDB reproducibly                                        | Ordered migrations upsert 26 evidence bundles and synthetic verified episodes                                             |
| FR-20 | Admit evidence strictly                                              | Tampered hashes, stale records, correlation mismatches, duplicate keys, and conflicts block execution                     |
| FR-21 | Prove containment                                                    | Result ties root cause and exact record IDs to policy, workflow, verification, economics, and monitor                     |
| FR-22 | Derive the resolution at runtime                                     | Selector validates option constraints, reconciles value components, scores every eligible option, and returns its formula |

## Scenario acceptance matrix

| Issue                     | Required evidence                                                      | Preferred resolution                                           | Boundary                             |
| ------------------------- | ---------------------------------------------------------------------- | -------------------------------------------------------------- | ------------------------------------ |
| Cosmetic damage           | Order, visual inspection, customer history, product quality, economics | Voluntary keep-item discount plus warranty                     | Customer confirms choice             |
| Early product failure     | Order, device diagnostics, warranty, batch quality, inventory          | Replace from unaffected batch                                  | Auto only for proven covered fault   |
| Missing delivery          | Carrier proof, address history, mailroom, customer history, inventory  | Reship plus carrier recovery                                   | Human verifies weak carrier evidence |
| Missing component         | Order bundle, package weight, item scan, bill of materials             | Ship only the missing part                                     | Do not replace the whole bundle      |
| High-value freight damage | Installer report, freight telemetry, recovery and disposal plan        | Coordinated replacement                                        | Supervisor approval                  |
| Safety incident           | Order/serial, symptom, safety database, recall status                  | Stop use and safety escalation                                 | Always human                         |
| Identity mismatch         | Order identity, serial registry, device/account proof                  | Denial with appeal                                             | Similarity cannot override identity  |
| High-return product       | Defect rate, reviews, customer facts, reverse-logistics economics      | Keep offer, repair, exchange, or refund according to condition | No coercive discount                 |
| Failed deployment         | Deployment, signed artifact, schema, telemetry, runbook                | Roll back and prove recovery                                   | Tested window and compatibility      |
| Database saturation       | Capacity, query, lock, change, and recovery-plan evidence              | Temporary read capacity with expiry                            | Exclude alternate causes             |
| Retry amplification       | Request metrics, traces, capacity, simulation, runbook                 | Bounded backoff, jitter, and queue protection                  | Preserve accepted requests           |
| Credential compromise     | Identity, audit, asset scope, forensics, incident plan                 | Scoped revoke, rotate, isolate, and incident                   | Human incident commander             |
| Dataset deletion          | Deletion audit, immutable backup, lineage, restore test, ownership     | Restore and validate in isolation                              | Human promotion approval             |

## Non-functional requirements

- **Safety:** The model cannot set permission or override deterministic boundaries.
- **Correctness:** Current issue evidence is evaluated before historical reliability.
- **Evidence integrity:** Only current, untampered, correlated, conflict-free records from admitted authorities satisfy a source contract.
- **Idempotency:** One logical request maps to one episode and at most one provider action.
- **Durability:** Production checkpoints, episodes, corrections, and outcomes survive Lambda cold starts.
- **Observability:** Responses carry request IDs and persisted evidence receipts.
- **Security:** Private S3 origin, HTTPS, throttling, least-privilege database role, and scoped Bedrock access.
- **Fairness:** Protected attributes are not inferred; behavioral history alone cannot establish fraud.
- **Reproducibility:** Deterministic adapters and synthetic data support credential-free validation.
- **Maintainability:** Types, formatting, linting, infrastructure validation, tests, and documentation checks run in one gate.

## Explicit non-goals

- Real payment, shipment, warranty, or fraud-provider execution. The current adapters execute simulated operations and return deterministic idempotent provider receipts.
- Inference of protected attributes
- Autonomous policy authoring or safety adjudication
- Cross-tenant memory retrieval
- Replacement of legal, compliance, or product-safety approval

## Release definition

A release is complete only when source, tests, migrations, API contract, operational documentation, and judge narrative describe the same behavior. Public AWS release additionally requires valid AWS credentials, Bedrock model access, a CockroachDB Cloud URL, Docker, and SAM CLI.
