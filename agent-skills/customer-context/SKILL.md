---
name: customer-context
description: Retrieve exact customer and operational facts for a resolution case. Use before proposing an exchange, shipment, repair, credit, denial, exception, or escalation that depends on order, delivery, product, warranty, seller, safety, or account evidence.
---

# Customer Context

Build the smallest verified customer timeline needed for the current decision.

## Workflow

1. Load the customer profile by exact ID.
2. Retrieve only the task-specific order, delivery, product, warranty, seller, safety, transaction, and account sources declared by the case.
3. Order events chronologically and retain source identifiers.
4. Separate verified facts from inferred patterns.
5. Return structured facts; do not recommend or authorize an action.

## Guardrails

- Use only operationally relevant attributes. Never infer protected characteristics.
- Treat recurrence as a signal to investigate, not proof of abuse.
- Distinguish one-time exceptions from reusable policy.
- Flag conflicting records instead of choosing one silently.
