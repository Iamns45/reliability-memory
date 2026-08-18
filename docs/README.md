# Reliability Memory documentation

> Status: Current
>
> Audience: Engineers, operators, security reviewers, and hackathon judges
>
> Owner: Reliability Memory maintainers
>
> Last reviewed: 2026-08-16

This directory is the canonical documentation set for Reliability Memory. Documents are organized by responsibility so product intent, implementation contracts, operational procedures, and submission material do not drift into one another.

## Start here

| If you need to…                                        | Read                                                                                              |
| ------------------------------------------------------ | ------------------------------------------------------------------------------------------------- |
| Understand the problem, scope, and acceptance criteria | [Product requirements](./product/PRODUCT_REQUIREMENTS.md)                                         |
| Understand the complete runtime and trust boundary     | [System design](./architecture/SYSTEM_DESIGN.md)                                                  |
| Edit the runtime architecture diagram                  | [draw.io source](./architecture/reliability-memory.drawio)                                        |
| Integrate with the backend                             | [API contract](./architecture/API_CONTRACT.md)                                                    |
| Understand CockroachDB ownership and relationships     | [Data model](./architecture/DATA_MODEL.md)                                                        |
| Set up a workstation and make a change                 | [Local development](./development/LOCAL_DEVELOPMENT.md)                                           |
| Understand the implementation with examples            | [Code walkthrough](./development/CODE_WALKTHROUGH.md)                                             |
| Run or extend verification                             | [Testing strategy](./development/TESTING_STRATEGY.md)                                             |
| Deploy the judge stack to AWS                          | [AWS deployment](./operations/AWS_DEPLOYMENT.md)                                                  |
| Diagnose or recover the service                        | [Operations runbook](./operations/RUNBOOK.md)                                                     |
| Review security assumptions and controls               | [Threat model](./security/THREAT_MODEL.md)                                                        |
| Rehearse or submit the project                         | [Demo script](./submission/DEMO_SCRIPT.md) and [Devpost copy](./submission/DEVPOST_SUBMISSION.md) |
| Resolve a domain term                                  | [Glossary](./product/GLOSSARY.md)                                                                 |

## Architecture decisions

Architecture decision records preserve the context and trade-offs behind durable choices:

1. [Use exactly one executable LangGraph node](./architecture/decisions/0001-one-executable-langgraph-node.md)
2. [Keep permission outside the language model](./architecture/decisions/0002-deterministic-permission-boundary.md)
3. [Use CockroachDB as the system of record](./architecture/decisions/0003-cockroachdb-system-of-record.md)
4. [Require current payment proof for payment claims](./architecture/decisions/0004-payment-first-duplicate-eligibility.md)
5. [Use issue-specific evidence and resolution economics](./architecture/decisions/0005-issue-specific-evidence-and-economics.md)
6. [Compile authorized actions into typed idempotent workflows](./architecture/decisions/0006-typed-idempotent-workflow-execution.md)
7. [Admit exact evidence and emit containment proof](./architecture/decisions/0007-strict-evidence-admissibility-and-containment.md)
8. [Derive the preferred resolution at runtime](./architecture/decisions/0008-derive-resolution-at-runtime.md)

## Documentation principles

- **One source of truth:** Product, API, data, operational, security, and submission concerns have separate owners and files.
- **Evidence over aspiration:** Current behavior is written in the present tense; future work is explicitly marked as planned.
- **Traceability:** Requirements point to tests or observable runtime evidence.
- **Safe examples:** Examples use synthetic customer and payment records and contain no credentials.
- **Change with code:** A behavior, endpoint, schema, policy, or deployment change is incomplete until its corresponding document is updated.
- **Recorded decisions:** A change to a durable architectural constraint requires a new decision record; accepted records are not rewritten to hide history.

## Document lifecycle

Every document declares a status, audience, owner, and review date. Use these status values:

| Status     | Meaning                                            |
| ---------- | -------------------------------------------------- |
| Proposed   | Under review and not yet authoritative             |
| Current    | Matches the implemented system                     |
| Superseded | Retained for history and linked to its replacement |
| Archived   | No longer operationally relevant                   |

The automated documentation check verifies the required structure, metadata, and local Markdown links as part of `npm run check`.
