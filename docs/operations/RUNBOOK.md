# Operations runbook

> Status: Current
>
> Audience: Operators, release engineers, and presenters
>
> Owner: Reliability Memory operations maintainers
>
> Last reviewed: 2026-08-16

## Health interpretation

An AWS judge deployment is ready only when `GET /health` reports:

| Field                       | Expected value             |
| --------------------------- | -------------------------- |
| `status`                    | `ok`                       |
| `memory`                    | `cockroachdb`              |
| `model`                     | `amazon-bedrock`           |
| `model_id`                  | `amazon.nova-lite-v1:0`    |
| `policy`                    | `customer-resolution-v5.0` |
| `mcp.status`                | `configured`               |
| `mcp.read_only`             | `true`                     |
| `mcp.required_for_autonomy` | `true`                     |
| `graph.node_count`          | `1`                        |
| `graph.typed_state`         | `AgentGraphState`          |
| `graph.checkpointer`        | `cockroachdb`              |

Use `X-Request-Id` to correlate browser, API Gateway, and Lambda logs.

## Failure matrix

| Symptom                         | Likely cause                                                                           | Safe response                                                                       |
| ------------------------------- | -------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------- |
| UI loads but catalog does not   | Same-origin route, Lambda, or database failure                                         | Check `/health`, API access logs, then Lambda logs with the request ID              |
| Catalog lacks evidence sources  | Migration 009 or catalog seed did not run                                              | Stop the demo run, apply ordered migrations, rerun idempotent seed                  |
| Health reports preview mode     | Secret or `USE_BEDROCK` is missing                                                     | Fix stack parameters; do not call it the AWS runtime                                |
| Bedrock access denied           | Model access, region, or IAM mismatch                                                  | Verify Nova Lite and Titan V2 access and scoped resources                           |
| Database connection fails       | Secret, network, certificate, or role                                                  | Validate the secret and least-privilege login                                       |
| MCP proof contracts to review   | Service-account key, Cluster Operator role, cluster ID, tool schema, or query mismatch | Run `scripts/verify_managed_mcp.py`; preserve the human-review fallback until fixed |
| Review cannot resume            | Wrong thread, missing checkpoint, or completed episode                                 | Use the original thread and inspect approval state                                  |
| Repeated request acts twice     | Idempotency regression                                                                 | Disable automatic execution, preserve evidence, investigate before replay           |
| Evidence bundle mismatches task | Bad seed/integration mapping                                                           | Route the case to human, fix data with a forward migration or integration patch     |
| Static UI is stale              | CloudFront invalidation or cache metadata                                              | Verify invalidation and no-cache `index.html`                                       |
| Reliability drops               | New failure, correction, recency, or novelty                                           | Inspect receipt and delayed outcomes; do not override policy manually               |

## Incident priorities

- **P0:** Unauthorized action, duplicate side effect, safety case auto-execution, corrupted audit evidence, or credential exposure.
- **P1:** Public API, catalog, or review flow unavailable during judging.
- **P2:** One experiment, receipt, or noncritical case unavailable.

For P0, stop automatic action execution, preserve request ID, idempotency key, episode, policy, source packet, action reference, outcomes, approvals, corrections, and receipt digest.

## Recovery rules

- Reconcile an idempotency key before replaying any provider action after an ambiguous commit.
- Correct schema behavior with a forward migration.
- Resume review only through its original graph thread.
- Preserve failed and delayed outcomes in reliability history.
- Roll back artifacts only to a source version compatible with the current schema.
- Rotate any credential exposed in source, logs, or an artifact.

## Demo readiness checklist

- [ ] Public CloudFront URL opens without sign-in.
- [ ] `/health` reports CockroachDB, Nova Lite, required read-only Managed MCP, policy v5.0, and one graph node.
- [ ] Catalog count is 26 and each case includes source evidence and resolution options.
- [ ] `CASE-184-26` returns a $60 keep offer with `VERIFY` and an episode ID.
- [ ] `CASE-202-26` shows a matching Managed MCP episode/vector receipt, executes a replacement from an unaffected batch, and verifies it.
- [ ] Missing-charger case selects a component shipment, not a full bundle replacement.
- [ ] Safety and high-value freight cases remain human-controlled.
- [ ] Warranty-grace review opens prefilled, resume returns a correction ID, and the later case replays it with `VERIFY`.
- [ ] Receipt, memory ablation, retry safety, policy comparison, envelope, and delayed outcome respond.
- [ ] Presenter uses only synthetic names and records shown in the product.
- [ ] The [demo script](../submission/DEMO_SCRIPT.md) matches the deployed source version.
