# ADR 0008: Derive the preferred resolution at runtime

> Status: Current
>
> Audience: Product owners, engineers, and policy reviewers
>
> Owner: Reliability Memory architecture maintainers
>
> Last reviewed: 2026-08-16

## Context

Issue-specific evidence bundles already contained multiple feasible remedies and their customer and company economics. They also contained a preselected remedy. Although deterministic policy correctly prevented the language model from granting permission, storing the preferred action made the most important customer-economics judgment look authored rather than derived.

## Decision

Case bundles store `resolution_options` and `resolution_constraints`, never a preferred answer. Each option supplies a bounded action amount, customer-value components, company cost, goal fit, eligibility, permission floor, safety flag, and explanatory evidence.

`resolution_selector.py` validates every option, rejects ineligible, under-fit, or over-limit candidates, reconciles value components, and ranks the remaining candidates with:

```text
selection score = goal fit × customer value ÷ company cost
```

Zero-cost, zero-value denial options score zero and remain available when they are the only eligible path. Deterministic tie breakers prefer better goal fit, greater customer value, lower company cost, and then stable source order.

The selector returns its method, score, rationale, eligible-option count, and every evaluated candidate. `ResolutionEvidence` carries those fields to policy, audit storage, receipts, and the UI.

Selection does not grant permission. The policy engine still independently enforces evidence grade, proposal agreement, safety and identity boundaries, customer-choice and human-review floors, delegated cost caps, novelty, and empirical reliability.

## Consequences

- A reviewer can reproduce why one remedy beat its alternatives.
- Customer value must reconcile to explicit components; for the cosmetic-damage case, `$95 = $60 adjustment + $35 expected warranty value`.
- Changing an input can change the remedy without changing code. Increasing the keep-offer cost in the cosmetic-damage packet causes replacement to win.
- Source integrations must provide feasible options and defensible economics; the selector is not a price-discovery model.
- Historical compatibility data may need reseeding because `selected_resolution` is no longer part of the evidence contract.

## Alternatives rejected

- **Keep a seeded recommendation:** simple, but obscures where the core economic judgment occurs.
- **Let the language model choose:** flexible, but breaks reproducibility and the policy trust boundary.
- **Minimize company cost only:** can select remedies that fail the customer's stated outcome.
- **Maximize customer value only:** can create unnecessary company loss when a lower-cost option fits the same goal.
