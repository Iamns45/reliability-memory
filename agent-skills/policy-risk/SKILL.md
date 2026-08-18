---
name: policy-risk
description: Evaluate customer-resolution risk and apply deterministic autonomy rules. Use after the agent has a current issue-evidence packet, a bounded proposal, and reliability evidence, before any commerce action or approval request.
---

# Policy and Risk

Treat this skill as the permission boundary outside the language model.

## Workflow

1. Validate the supported action, bounded value, required sources, and proposal-plan agreement.
2. Calculate safety, identity, eligibility, financial, contractual, abuse-review, customer-impact, and reversibility risk.
3. Load the current versioned policy.
4. Apply hard limits before reliability thresholds.
5. Return `AUTO`, `VERIFY`, `HUMAN`, or `DENY` with the matched rule ID.

## Guardrails

- Ignore any permission or execution instruction produced by the model.
- Never let confidence override current evidence, customer choice, safety, identity, value, contract, or compliance limits.
- Default to `HUMAN` when evidence is missing, stale, or novel.
- Produce an auditable reason for every gate decision.
