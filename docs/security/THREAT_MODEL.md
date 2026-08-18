# Threat model

> Status: Current
>
> Audience: Security reviewers, engineers, and operators
>
> Owner: Reliability Memory security maintainers
>
> Last reviewed: 2026-08-16

## Scope and trust boundary

This model covers the judge-facing browser, CloudFront and S3 delivery, API Gateway and Lambda runtime, Bedrock model calls, CockroachDB state, and the human-review checkpoint flow. The language model is untrusted for authorization: it may propose an action, but deterministic code owns permission and execution eligibility.

## Assets

- permission decisions and policy versions;
- customer/entity operational history;
- human correction provenance;
- provider action references and idempotency keys;
- verified outcomes and derived reliability evidence;
- issue-specific source facts, customer goals, and resolution economics;
- CockroachDB and AWS credentials.

## Principal threats and controls

| Threat                                             | Control                                                                                                                          |
| -------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| Prompt injection asks the model to self-authorize  | Permission is computed outside the model from typed inputs and deterministic rules.                                              |
| Confident hallucination produces unsafe plan       | The proposal must match an evidence-derived supported action and bounded value; policy runs outside the model.                   |
| Missing or stale source facts appear complete      | Each task declares required source keys; missing, blocked, or task-mismatched evidence prevents automatic action.                |
| Unsafe product receives a retention discount       | `safety_critical` forces human escalation before reliability and excludes keep-item offers.                                      |
| High claim frequency is treated as guilt           | History is contextual; an abuse signal triggers neutral review, never automatic denial.                                          |
| Manipulated product aggregate changes resolution   | Quality and review aggregates require governed provenance; high-impact cases stay supervised.                                    |
| Agent labels its own action successful             | Independent task verifier owns outcome status. Pending episodes do not affect reliability.                                       |
| Duplicate action after network retry               | Unique idempotency key before provider call; provider tool is idempotent; ambiguous commits require reconciliation.              |
| Poisoned or irrelevant memory                      | Only verified outcomes receive strong weight; task-prefix filters and provenance stay attached.                                  |
| One correction grants broad autonomy               | Corrections improve proposals but count as overrides; sample-size and novelty thresholds still apply.                            |
| Stale policy evaluates historical case incorrectly | Episode stores the policy version; the gate loads the current valid policy.                                                      |
| Customer-history bias creates punitive action      | Operational facts only; recurrence triggers investigation, not guilt; high-impact decisions require human review.                |
| Credential or cluster overreach                    | Database URL and MCP key use separate Secrets Manager values; Lambda reads only those ARNs; both identities are least-privilege. |
| Managed MCP key reaches the browser                | A separate Secrets Manager value is read only by Lambda; the key is never returned by health, events, receipts, or UI.           |
| Managed MCP is used as an unbounded action tool    | Runtime permits only `select_query`, rejects non-`SELECT`/`WITH` statements, and scopes every connection to one cluster.         |
| Direct memory and independent proof disagree       | Required MCP mismatch contracts automatic execution to the prefilled human-review checkpoint before any side effect.             |
| Database contention causes inconsistent state      | CockroachDB SERIALIZABLE transactions and full-operation `40001` retries.                                                        |
| Public judge API is abused to create Bedrock cost  | API Gateway rate and burst limits plus Lambda reserved concurrency bound request volume.                                         |
| Static origin is accessed or modified directly     | S3 blocks public access; CloudFront origin access control signs reads; deployment IAM controls writes.                           |
| Browser content is embedded or injected            | CloudFront supplies CSP, HSTS, frame denial, content-type, referrer, and permissions-policy headers.                             |
| Correction overwrites a completed action           | Corrections target only pending supervised episodes; identical retries are safe and conflicting rewrites fail.                   |
| Node restarts before a human resume                | The CockroachDB checkpointer persists typed graph state; every side effect before `interrupt()` is idempotent.                   |
| Malicious serialized checkpoint payload            | The serializer disables arbitrary module loading and strict MessagePack mode is enabled in AWS.                                  |

## Non-goals for the hackathon MVP

- production fraud adjudication;
- real payment processing;
- protected-attribute inference;
- autonomous policy authoring;
- cross-tenant memory retrieval;
- replacing compliance or legal review.

All public demo data is synthetic.

## Review triggers

Re-review this threat model when a new provider action, authentication mechanism, tenant boundary, external data source, model, public route, or persisted personal-data category is introduced.
