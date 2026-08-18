# Code walkthrough and dry runs

> Status: Current
>
> Audience: Engineers, reviewers, and technical judges
>
> Owner: Reliability Memory engineering maintainers
>
> Last reviewed: 2026-08-16

This guide explains every execution block in source order. Literal commentary on every physical line would become wrong after formatting, so the walkthrough groups adjacent lines that implement one invariant and names the exact function responsible.

## Source map

| Concern          | File                                      | Responsibility                                                           |
| ---------------- | ----------------------------------------- | ------------------------------------------------------------------------ |
| Case definitions | `services/api/app/case_catalog.py`        | 26 consumer and enterprise records, evidence, options, and economics     |
| Domain types     | `services/api/app/domain.py`              | Cases, proposals, evidence, permission, workflows, containment, outcomes |
| Remedy selector  | `services/api/app/resolution_selector.py` | Validate and rank feasible options without reading a stored answer       |
| Evidence build   | `services/api/app/resolution_evidence.py` | Convert repository JSON into typed `ResolutionEvidence`                  |
| Agent sequence   | `services/api/app/runtime.py`             | Load, evaluate, retrieve, propose, gate, persist, act, verify, and learn |
| Permission       | `services/api/app/policy.py`              | Deterministic v5.0 rules and v4.9 comparison baseline                    |
| Typed graph      | `services/api/app/graph_runtime.py`       | One node, streaming, checkpointing, interrupt, and resume                |
| Storage          | `services/api/app/repository.py`          | CockroachDB and deterministic in-memory adapters                         |
| API              | `services/api/app/main.py`                | Request validation, routes, composition, and SSE                         |
| UI client        | `app/runtime-client.ts`                   | Typed catalog fetch, run stream, resume stream, and experiments          |
| UI workbench     | `app/reliability-dashboard.tsx`           | Real case file, evidence, economics, result, review, and lab             |

## 1. Case catalog: define the investigation before the answer

`_source()` creates one evidence source with a stable key, analyst label, status, summary, facts, admitted authority, SHA-256 integrity digest, observation time, maximum age, and conflict list. `_case()` adds the source system, immutable record ID, exact case/customer/task correlation, decision snapshot time, and derives `evidence_required` from the source keys. That prevents the displayed checklist from drifting from policy and gives the runtime enough data to reject tampered, stale, or misattached records.

For example, the early blender failure requires:

```text
order + diagnostics + warranty + product_quality + customer_history + inventory
```

Its options include an $89 replacement with $48 expected company cost and a slower warranty repair. These numbers are evidence inputs, not a model-generated discount. The catalog stores no preferred option; the runtime selector derives replacement from the current option economics and constraints.

## 2. Domain types: make invalid state difficult to represent

`ResolutionEvidence` records the issue type, completeness, autonomy eligibility, evidence grade and snapshot, required and completed sources, source facts, computed action, bounded amount, company cost, customer value and its components, selection method, score and rationale, permission floor, auto-cost cap, safety flag, goal, guardrail, blockers, alternatives, reason, and lesson.

`AgentProposal` intentionally has no permission field. `PermissionDecision` is produced separately. `ContainmentProof` binds exact evidence IDs to policy, workflow, verification, economics, and monitoring. `AgentRun` joins the `CustomerCase`, model proposal, reliability evidence, deterministic permission, current evidence, retrieved experiences, containment, execution, and verification into one auditable result.

## 3. Evidence evaluator: turn heterogeneous JSON into a strict packet

`assess_resolution_evidence(case, customer_context)` executes these checks:

1. Read `case_evidence` from authoritative customer context, falling back to server case metadata.
2. Ignore a bundle whose `issue_type` does not match `case.task_type`.
3. Parse the evidence snapshot time and convert source objects to immutable tuples.
4. For each source, validate status, authority, source system, record ID, recomputed SHA-256 digest, observation time, maximum age, exact case/customer/task correlation, and conflicts.
5. Reject duplicate source keys and calculate required keys that have no admissible record.
6. Assign `BLOCKED` when admission fails, `REVIEW` when admissible warning evidence exists, and `EXACT` only when every required record passes without warning.
7. Pass every option and the case constraints to `select_resolution()`.
8. Validate finite economics, customer-value component reconciliation, goal fit, eligibility, permission floors, safety, and case cost limits.
9. Score every eligible option with `goal_fit × customer_value ÷ company_cost`; deterministic tie breakers prefer better goal fit and value, then lower cost.
10. Convert the selected option's permission floor to `DecisionMode`; unknown values safely become `HUMAN`.
11. Preserve the evaluated alternatives, formula, score, positive facts, blockers, goal, guardrail, reason, and lesson.

The selector rejects negative or non-finite economics and refuses value components that do not sum to the declared customer value. The resulting `evidence_complete` is true only when required sources exist and every required record is admissible. `autonomy_eligible` additionally requires that no source carries a warning.

Example: a missing-delivery source with status `warning` still tells policy that the carrier scan exists and is off-location. The packet receives grade `REVIEW`, never `EXACT`, so it cannot auto-execute even if historical reliability is high.

## 4. Application composition: swap infrastructure, keep rules

`create_app()` loads settings and `_build_agent()` chooses adapters:

```text
DATABASE_URL present  -> CockroachMemoryRepository
DATABASE_URL absent   -> InMemoryMemoryRepository

USE_BEDROCK=true      -> BedrockReasoner + TitanEmbeddingProvider
USE_BEDROCK=false     -> DeterministicDemoReasoner + DeterministicEmbeddingProvider
```

Both modes use the same evidence evaluator, policy, graph state, events, validation, and response shape. Production changes the dependencies, not the decision boundary.

Pydantic request models reject unknown fields. The middleware creates an `X-Request-Id`, measures duration, and writes structured request logs. `_graph_state()` reloads a supplied catalog ID from the repository so browser fields cannot tamper with the case.

## 5. One typed LangGraph node

The graph constructor performs exactly three topology operations:

```text
add_node("reliability_memory_agent", _agent_node)
add_edge(START, "reliability_memory_agent")
add_edge("reliability_memory_agent", END)
```

`AgentGraphState` requires thread ID, request ID, serialized case, and status. Result, review summary, human resolution, and correction ID appear only when those stages occur. `stream()` combines LangGraph custom events and state updates; FastAPI converts each yielded event into SSE. There are no browser timers pretending to be backend progress.

## 6. Agent execution, statement by statement

`ReliabilityMemoryAgent.run()` follows this fixed order:

1. Emit `context.started`.
2. Load the customer, operational timeline, and authoritative case evidence.
3. Replace browser account, region, and contract copies with repository values.
4. Emit `context.completed` with the loaded event count.
5. Emit `case_evidence.started` and build `ResolutionEvidence`.
6. Emit `case_evidence.completed` with the actual packet.
7. Emit `evidence.admissibility.completed` with grade, snapshot, exact record IDs, autonomy eligibility, and blockers.
8. Evaluate payment evidence only for the compatibility payment task; other tasks report not applicable.
9. Retrieve task-filtered verified episodes and corrections, then calculate reliability.
10. Ask the reasoner for an action from current facts and retrieved evidence.
11. Replay a verified warranty-grace correction when its narrow lesson matches.
12. Emit the proposal; then call deterministic policy.
13. Compile the proposal into a typed, issue-specific `WorkflowPlan` and emit `workflow.planned`.
14. Create the pending containment proof and `AgentRun`, then persist the decision before any external action.
15. If the idempotency key already exists, return the same episode and do not call a provider.
16. Withhold `VERIFY` and `HUMAN` actions for graph review.
17. Execute `AUTO` and exact evidence-backed denial/appeal workflows with the same idempotency key.
18. Independently verify the immutable workflow result, finalize containment proof, and persist the outcome.

## 7. Policy v5.0: why a small value is not enough

`DeterministicPolicyEngine.evaluate()` first rejects negative, non-finite, or over-claim values. An abuse signal routes to neutral human review. `_evaluate_resolution()` then applies the issue packet:

```text
proposal mismatch       -> DENY, or HUMAN when a hard human plan must be prefilled
selected denial         -> DENY with evidence/appeal rationale
missing required source -> HUMAN
review-grade evidence   -> VERIFY when an AUTO floor would otherwise apply
safety-critical         -> HUMAN
human permission floor  -> HUMAN
verify floor            -> VERIFY
company cost above cap  -> VERIFY
98%+, 100+ cases, LOW   -> AUTO
90%+ and not high risk  -> VERIFY
otherwise               -> HUMAN
```

The warranty-grace rule is deliberately narrower: one relevant verified correction moves the same exception from `HUMAN` to `VERIFY`, never directly to `AUTO`.

## 8. Containment proof, field by field

`_containment_proof()` first copies the exact admitted record IDs, evidence grade, required/admissible counts, root-cause reason, policy rule, customer value, company cost, and intended autonomy level. Before permission it reports `EXECUTION_PENDING` or `AWAITING_CONFIRMATION`. After execution and independent verification it adds the stable workflow ID, completed-operation count, verified state, estimated human time avoided, and a seven-day reopen deadline. Supervised completions are labeled `CONTAINED_AFTER_APPROVAL`; automatic and exact evidence-backed denial workflows are labeled `CONTAINED`.

## 9. Human interrupt and resume

When permission is supervised, `_review_summary()` copies the request, proposal, current evidence packet, historical statistics, nearest episode IDs, policy rule and reasons, evidence-derived suggestion, rationale, and reusable lesson. The graph saves the summary and calls `interrupt()`.

On resume, `_resolve_human_action()` accepts one of three intents:

- `approve_suggestion`: use the evidence-derived resolution;
- `accept_proposal`: use the bounded proposal;
- `reject`: persist a denial.

Optional edits must use a supported action, remain between zero and the case claim, and include meaningful reason and lesson text. The correction is embedded and persisted against the paused episode. `execute_reviewed_workflow()` then rebuilds the typed plan from the approved action, runs it with `review:{episode_id}` idempotency, independently verifies it, and returns the correction plus workflow IDs and step receipts.

## Dry run A: Srinivas receives a choice, not an automatic discount

Case: `CASE-184-26`, dented but functional $249 espresso machine.

1. Order proves delivery yesterday.
2. Photo and power-on evidence classify the dent as cosmetic, not safety-related.
3. Customer history shows 18 orders, one return, and no abuse flag.
4. Product evidence shows 11.8% returns versus a 4.2% category baseline, with transit denting common.
5. Economics compares: keep offer costs $60; replacement costs $152; full return costs $191.
6. Customer value 95 reconciles to a $60 immediate adjustment plus $35 expected warranty coverage.
7. The selector computes goal-adjusted value per company dollar for all three eligible options and derives the keep offer at runtime; no selected answer is stored in the bundle.
8. Policy does not say “under $100, auto.” The computed plan has a `VERIFY` floor because Srinivas must voluntarily choose to keep the damaged product.
9. The graph pauses with every fact, formula, and alternative prefilled.

## Dry run B: product stops working after two days

Case: `CASE-202-26`, $89 blender with error E17.

1. Serial-linked diagnostics reproduce motor-controller failure; reset does not fix it.
2. Warranty has 363 days remaining.
3. Batch B4-26A has 8.6% defects versus 1.3% baseline.
4. Inventory has an unaffected B4-26C replacement with $48 company cost.
5. The plan selects replacement, bypasses repetitive troubleshooting, and flags the bad batch.
6. Evidence is complete, current risk is low, historical evidence exceeds 100 cases and 98%, and cost is under the task cap.
7. Policy returns `AUTO`; the decision persists first, then one replacement action executes and is verified.

## Dry run C: missing laptop charger

Case: `CASE-205-26`, $1,299 laptop bundle.

1. The order bill of materials requires a 65W charger.
2. Pack-station weight is 310g below expected and the charger scan is absent.
3. The laptop serial is correct and the primary product works.
4. Shipping a $29-cost charger creates the required $49 customer value; replacing the $1,299 bundle would cost about $910.
5. Policy evaluates the selected component action and company cost—not the laptop's headline price—and permits the proven low-risk shipment.

## Dry run D: safety beats retention

Case: `CASE-207-26`, a device emits smoke.

1. Safety-specific sources load the serial, symptom, incident history, and protocol.
2. `safety_critical=true` forces `HUMAN` before reliability can authorize anything.
3. The only acceptable suggestion is to stop use and escalate to the safety owner.
4. No keep-item discount or scripted troubleshooting is offered.

## Dry run E: correction changes future warranty behavior

Cases: `CASE-771-26` followed by `CASE-841-26`.

1. A known defect appears shortly after warranty expiry; current policy initially requires human review.
2. The reviewer approves the prefilled repair and records a narrow 14-day grace-period lesson.
3. Resume persists a correction ID on the original episode.
4. The later comparable case retrieves that correction and emits `correction.replayed`.
5. The proposal changes from generic service recovery to `warranty_repair`.
6. Policy returns `VERIFY`: the lesson changes behavior, while more verified replay outcomes are still required for autonomy.

## Dry run F: retry and delayed outcome

For retry injection, two submissions use the same idempotency key. The first persists and may execute; the second returns the same episode with `side_effect_executed=false`. One logical request therefore creates at most one provider action.

For delayed simulation, a later adverse result attaches to an already verified episode. The repository keeps both observations, reliability recalculates lower for that task, and the response reports whether future permission may contract.

## Dry run G: failed enterprise deployment is contained

Case: `CASE-302-26`, release 7.18.0 fails production health checks.

1. Deployment control proves the failing release and rollout window.
2. The artifact registry proves release 7.17.4 is signed, immutable, and previously healthy.
3. The schema registry proves rollback compatibility; service telemetry isolates timing; the runbook proves pre-authorization.
4. All five records pass authority, SHA-256 integrity, freshness, entity correlation, uniqueness, and conflict checks, so grade is `EXACT`.
5. Policy returns `AUTO` because the action matches the evidence plan, company cost is $18, risk is low, and comparable reliability is 99.2% across 500 outcomes.
6. The workflow freezes rollout, restores the healthy artifact, verifies recovery, opens the root-cause record, and notifies owners.
7. The containment proof returns all five source IDs, the policy rule, five step receipts, stable workflow ID, independent verification, $950 customer value, $18 company cost, 36 minutes avoided, and the reopen-monitor deadline.

## Invariants to preserve

- One executable graph node with typed state
- Repository-authoritative catalog and evidence
- Authority, integrity, freshness, correlation, uniqueness, and conflict checks before evidence admission
- Issue-specific current facts before historical reliability
- Model proposal separate from permission
- Customer choice preserved for retention offers
- Safety and identity boundaries protected
- Decision persistence before external action
- External action outside database transactions
- Independent verification before reliability credit
- Exact evidence IDs bound to policy and workflow in containment proof
- Idempotent run and resume behavior
