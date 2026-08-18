# API contract

> Status: Current
>
> Audience: Frontend, backend, integration, and QA engineers
>
> Owner: Reliability Memory API maintainers
>
> Last reviewed: 2026-08-16

FastAPI is the sole browser contract. The generated schema is available at `/docs` while the service is running.

## Conventions

- Unknown JSON fields are rejected.
- Monetary values are finite, non-negative where appropriate, and rounded at the action boundary.
- Mutating runs require an `Idempotency-Key` containing 8–128 allowed characters.
- Every response carries `X-Request-Id`; callers may supply it for correlation.
- Stream endpoints use `text/event-stream`; progress events originate in backend stages.
- When `case_id` is supplied, repository facts and its evidence bundle are authoritative. Browser copies cannot replace them.
- The frontend displays the permission returned by the API and contains no shadow policy.

## Endpoints

| Method | Path                                  | Purpose                                   | Important result                                              |
| ------ | ------------------------------------- | ----------------------------------------- | ------------------------------------------------------------- |
| `GET`  | `/health`                             | Runtime capability and dependency mode    | model, Managed MCP, policy v5.0, one-node graph, checkpointer |
| `GET`  | `/v1/cases/catalog`                   | Joined analyst queue                      | 26 consumer and enterprise case files with source evidence    |
| `POST` | `/v1/cases/run`                       | Synchronous execution                     | completed result or paused review packet                      |
| `POST` | `/v1/cases/stream`                    | Stream a new graph execution              | ordered backend SSE events                                    |
| `POST` | `/v1/cases/{thread_id}/resume`        | Resume a paused checkpoint                | approved execution, verification, and correction ID           |
| `POST` | `/v1/cases/{thread_id}/resume/stream` | Stream checkpoint resume                  | review, workflow-step, verification, and completion events    |
| `POST` | `/v1/corrections`                     | Compatibility route for direct correction | persisted correction ID                                       |
| `GET`  | `/v1/receipts/{run_id}`               | Read one audit record                     | version, episode ID, digest, canonical record                 |
| `GET`  | `/v1/reliability/envelope`            | Inspect earned-autonomy contexts          | policy and exact context decisions                            |
| `GET`  | `/v1/reliability/autonomy-ledger`     | Inspect hash-chained authority records    | dated entries, previous hashes, and ledger head               |
| `GET`  | `/v1/impact/summary`                  | Aggregate verified outcome economics      | customer value, selected cost, and refund-first comparison    |
| `POST` | `/v1/experiments/memory-ablation`     | Compare with and without memory           | reliability and permission delta                              |
| `POST` | `/v1/experiments/policy-comparison`   | Evaluate one packet under two policies    | v4.9 and v5.0 decisions                                       |
| `POST` | `/v1/experiments/idempotency`         | Submit one logical request twice          | same episode and provider-action proof                        |
| `POST` | `/v1/experiments/evidence-fault`      | Corrupt a copied evidence packet safely   | before/after grade, permission, blockers, no side effects     |
| `POST` | `/v1/outcomes/delayed`                | Attach a later verified consequence       | reliability before and after                                  |

## Catalog evidence bundle

Each catalog record includes:

```json
{
  "case_id": "CASE-184-26",
  "task_type": "damaged_item_keep_offer",
  "customer_segment": "consumer",
  "evidence_as_of": "2026-08-16T20:00:00Z",
  "customer_goal": "Receive fair value without waiting for a replacement.",
  "business_guardrail": "Ask before applying a keep-item discount.",
  "evidence_required": [
    "order",
    "damage_photo",
    "customer_history",
    "product_quality",
    "economics"
  ],
  "evidence_sources": [
    {
      "key": "damage_photo",
      "label": "Damage inspection",
      "status": "verified",
      "summary": "Cosmetic side-panel dent",
      "facts": ["No water-path damage", "Power-on video passes"],
      "authority": "system_of_record",
      "source_system": "damage_inspection",
      "source_record_id": "EV-CASE-184-26-damage_photo",
      "integrity": "sha256_verified",
      "observed_at": "2026-08-16T18:00:00Z",
      "max_age_seconds": 2592000,
      "conflicts": [],
      "correlation": {
        "case_id": "CASE-184-26",
        "customer_id": "C-184",
        "task_type": "damaged_item_keep_offer"
      }
    }
  ],
  "resolution_options": [
    {
      "action": "partial_refund",
      "amount": 60,
      "customer_value": 95,
      "company_cost": 60,
      "goal_fit": 1.0,
      "eligible": true,
      "permission_floor": "VERIFY",
      "value_components": [
        { "label": "Immediate price adjustment", "amount": 60 },
        { "label": "Two-year warranty coverage", "amount": 35 }
      ],
      "label": "$60 back + two-year warranty; customer keeps item"
    }
  ],
  "resolution_constraints": {
    "default_permission_floor": "VERIFY",
    "auto_cost_cap": 250,
    "resolution_cost_cap": 249,
    "minimum_goal_fit": 0,
    "safety_critical": false
  }
}
```

The evaluator recomputes the source hash and validates authority, system and record provenance, observation time against the decision snapshot, configured freshness window, exact case/customer/task correlation, uniqueness, and conflicts. A failed check produces grade `BLOCKED` and routes to human review. A complete bundle containing a warning produces grade `REVIEW`; it can support a supervised plan but can never grant `AUTO`. Only a complete, warning-free bundle receives grade `EXACT`.

No preferred action is stored in the bundle. `resolution_selector.py` validates option eligibility, goal fit, safety, permission floors, customer-value components, and case cost limits, then ranks eligible options by goal-adjusted customer value per company dollar. The run response returns `selection_method`, `selection_score`, `selection_rationale`, the selected option, and every evaluated alternative. Deterministic policy evaluates the computed selection separately; selection never grants permission.

Every run response also contains `counterfactual`. The runtime applies the listed changes to copies of the typed inputs and calls policy v5.0 again. `validated_by_policy=true` therefore means the reported changes actually produced `AUTO`; safety, identity, customer-choice, and explicit human floors are returned in `hard_boundaries` instead of being presented as negotiable thresholds.

## Run a catalog case

```http
POST /v1/cases/stream HTTP/1.1
Content-Type: application/json
Idempotency-Key: judge-case-202-0001

{
  "case_id": "CASE-202-26",
  "customer_id": "C-202",
  "request_text": "Run the authoritative catalog case.",
  "requested_amount": 89,
  "memory_enabled": true
}
```

## Stream protocol

Events contain an SSE type plus JSON data:

```text
event: policy.completed
data: {"type":"policy.completed","data":{"mode":"AUTO","rule_id":"earned-resolution-autonomy","policy_version":"customer-resolution-v5.0"}}
```

A typical automatic run emits:

```text
graph.started
context.started
context.completed
case_evidence.started
case_evidence.completed
evidence.admissibility.completed
memory.started
memory.completed
proposal.started
proposal.completed
policy.started
policy.completed
workflow.planned
decision.persisted
mcp.verification.started
mcp.verification.completed
action.started
workflow.started
workflow.step.started
workflow.step.completed
workflow.completed
action.completed
verification.started
verification.completed
run.result
graph.completed
```

A supervised run emits `workflow.planned`, `action.withheld`, `run.result`, `review.required`, and `graph.paused`. A successful resume emits `graph.started`, `review.resumed`, the actual workflow and verification events, `run.result`, and `graph.completed` for the same thread.

When AWS requires Managed MCP and the independent proof fails, the stream adds `policy.contracted`; the result permission is `HUMAN`, the action is withheld, and the graph creates a prefilled review checkpoint. `result.mcp_verification` contains the MCP tool, cluster scope, observed episode and policy, direct-versus-MCP vector neighbor IDs, match set, failure reason when applicable, timestamp, and SHA-256 receipt hash. It never contains the service-account key.

`result.workflow_plan` is the pre-side-effect contract. Each planned step identifies its target system, operation, detail, and reversibility. After execution, `result.execution` adds a stable `workflow_id`, step-level status and provider references, workflow artifacts such as a tracking or authorization reference, and the amount actually executed.

`result.containment` is the case-level proof. It contains containment status and level, root cause, evidence grade and exact source record IDs, required/admissible counts, policy rule, workflow ID, operation count, independent verification state, customer value, company cost, estimated human time avoided, and the reopen-monitor deadline.

## Human resume

The review packet includes the request, customer goal, proposal, evidence packet, options, economics, nearest episodes, Managed MCP proof, policy reasons, recommended resolution, reusable lesson, and exact workflow plan. Confirm it with:

```json
{
  "resolution": "approve_suggestion"
}
```

The reviewer may instead accept the proposal, reject it, or edit `action_type`, `amount`, `reason`, and `lesson`. The server validates the action and value, attaches the correction to the paused episode, rebuilds the workflow from the approved action, executes it under `review:{episode_id}`, verifies the result, and resumes the original graph checkpoint.

## Error behavior

| Status | Meaning                                                             |
| ------ | ------------------------------------------------------------------- |
| `400`  | Invalid idempotency key                                             |
| `404`  | Unknown catalog case or receipt                                     |
| `409`  | Episode is complete, not reviewable, or conflicts with a correction |
| `422`  | Shape, enum, range, or cross-field validation failed                |
| `500`  | Dependency or runtime failure; correlate with `X-Request-Id`        |

## Compatibility

Adding an optional response field is backward-compatible. Renaming a field, changing an enum, or altering idempotency, evidence, action, or money semantics requires a coordinated API, UI, test, and documentation update.
