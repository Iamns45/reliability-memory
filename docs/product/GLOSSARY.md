# Glossary

> Status: Current
>
> Audience: All contributors and reviewers
>
> Owner: Reliability Memory maintainers
>
> Last reviewed: 2026-08-16

| Term                   | Meaning                                                                                                                                                               |
| ---------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Agent                  | The single resolution-operations workflow that observes, admits evidence, retrieves, proposes, gates, acts, verifies, and learns                                      |
| Executable node        | A LangGraph node that runs business logic; START and END are framework sentinels                                                                                      |
| Skill                  | A cohesive capability invoked inside the one business node, not a separate graph node                                                                                 |
| Case evidence          | Typed, issue-specific current facts required before a resolution can be authorized                                                                                    |
| Evidence source        | One authoritative system or observation, such as an order, device diagnostic, carrier scan, product-quality aggregate, or package-weight record                       |
| Evidence admissibility | Validation of authority, provenance, integrity, freshness, entity correlation, uniqueness, and conflicts before a source can satisfy a case contract                  |
| Evidence grade         | `EXACT` for complete warning-free proof, `REVIEW` for admissible proof with warnings, or `BLOCKED` for failed admission                                               |
| Resolution option      | A feasible bounded action with reconciled customer-value components, company cost, goal fit, eligibility, and operational consequences                                |
| Customer value         | The sum of auditable benefit components delivered by a resolution; for the cosmetic-damage case, `$60 adjustment + $35 expected warranty coverage = $95`              |
| Company cost           | The expected economic cost of the action after recovery or retained value where represented by the scenario                                                           |
| Goal fit               | A source-supplied 0–1 measure of how completely an option satisfies the customer's stated outcome, including effort or delay                                          |
| Selection score        | Deterministic option ranking calculated as `goal fit × customer value ÷ company cost`; it selects a remedy but never grants permission                                |
| Business guardrail     | A deterministic constraint that protects safety, eligibility, customer choice, or company exposure                                                                    |
| Reliability            | A deterministic score derived from verified outcomes, overrides, context distance, recency, sample uncertainty, and novelty                                           |
| Reliability envelope   | Exact contexts in which evidence and policy permit a level of autonomy; never a single global agent score                                                             |
| Permission             | The deterministic result `AUTO`, `VERIFY`, `HUMAN`, or `DENY`                                                                                                         |
| `AUTO`                 | The exact bounded action may execute idempotently and then be independently verified                                                                                  |
| `VERIFY`               | Evidence supports the plan, but a reviewer must confirm customer choice or an explicit exception                                                                      |
| `HUMAN`                | Safety, novelty, missing facts, abuse review, high impact, or another hard boundary requires judgment                                                                 |
| `DENY`                 | Current facts establish that the proposed action violates an identity, eligibility, action, or value invariant; the customer receives an appeal path where applicable |
| Episode                | Persisted context, proposal, permission, action state, policy version, and outcome state                                                                              |
| Outcome                | Immediate or delayed independently observed evidence attached to an episode                                                                                           |
| Correction             | Persisted human resolution, reason, and reusable lesson attached to a supervised episode                                                                              |
| Correction replay      | Retrieval and deterministic application of a verified lesson to a later comparable case                                                                               |
| Evidence receipt       | Versioned canonical persisted record plus its SHA-256 digest                                                                                                          |
| Containment proof      | Typed record binding root cause and exact evidence IDs to policy, workflow, verification, economics, time avoided, and reopen monitoring                              |
| Idempotency key        | Stable caller key mapping one logical request to one episode and preventing repeat provider actions                                                                   |
| Delayed outcome        | A consequence observed after immediate verification, such as a chargeback, repeat failure, or recovery success                                                        |
| Policy version         | Immutable rule-set identifier, such as `customer-resolution-v5.0`                                                                                                     |
| Preview adapter        | Local runtime that preserves contracts without requiring cloud credentials                                                                                            |
