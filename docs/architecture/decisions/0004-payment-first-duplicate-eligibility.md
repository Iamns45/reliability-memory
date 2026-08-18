# ADR 0004: Require current payment proof before reliability

> Status: Accepted compatibility decision
>
> Audience: Product, policy, backend, and security contributors
>
> Owner: Reliability Memory maintainers
>
> Last reviewed: 2026-08-16

## Context

The earlier amount-first policy could make a small request appear safe without proving that a duplicate payment existed. A customer statement, model proposal, or similar historical episode cannot independently establish the present payment state. Goodwill credit is also unrelated to whether a second charge must be refunded.

## Decision

The payment adapter evaluates duplicate-charge eligibility before reliability or account exposure:

1. Load current payment rows from the authoritative customer context.
2. Require exactly two matching rows for one provider, merchant reference, subscription, billing period, payment method, amount, and currency.
3. Require both rows to be settled within ten minutes.
4. Reject any pair with prior refund, reversal, dispute, or chargeback state.
5. Require the request and proposal to equal the confirmed duplicate amount.
6. Only then consider historical reliability and the account-specific execution cap.

Missing or ambiguous proof yields `HUMAN`; a mismatched proposal yields `DENY`. A goodwill credit remains visible context and is never netted from the duplicate amount.

## Consequences

- Small amount alone never grants autonomy.
- The $79 confirmed duplicate refunds the full $79.
- Different payment methods, pending authorizations, prior remediation, late captures, disputes, triple captures, and a missing second row remain supervised.
- This specialized adapter remains valid when a payment claim is added through an integration, but it no longer defines the case catalog.
- Policy v5.0 generalizes the same current-evidence-first principle through [ADR 0005](./0005-issue-specific-evidence-and-economics.md).

## Compliance evidence

Payment-evidence unit tests cover each blocker. Catalog tests separately verify the broader issue-specific evidence model introduced by ADR 0005.
