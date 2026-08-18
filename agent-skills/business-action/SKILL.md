---
name: business-action
description: Execute an authorized customer-resolution action through an idempotent business tool. Use only after policy-risk returns AUTO, or after a recorded human approval permits the exact resolved action.
---

# Business Action

Execute exactly the action and amount authorized by the gate.

## Workflow

1. Require an authorization record and idempotency key.
2. Revalidate that the action matches the authorized proposal.
3. Call the appropriate commerce provider outside the database transaction.
4. Capture the immutable provider reference and actual amount.
5. Return execution facts to the outcome verifier.

## Guardrails

- Never act on `VERIFY`, `HUMAN`, or `DENY` without a resolved approval.
- Never expand scope, amount, or recipient after authorization.
- Reconcile ambiguous provider results before retrying.
- Do not label the action successful; verification is independent.
