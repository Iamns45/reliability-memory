# ADR 0002: Keep permission outside the language model

> Status: Current (decision: Accepted)
>
> Audience: Architecture, policy, security, and backend contributors
>
> Owner: Reliability Memory maintainers
>
> Last reviewed: 2026-08-16

## Context

A model can propose plausible actions and explanations, but its confidence is neither independent evidence nor a safe authorization mechanism. Historical similarity can also retrieve useful cases without proving that the current request is legitimate.

## Decision

The model produces an `AgentProposal` only. A deterministic policy engine receives typed current-case evidence, proposal values, verified reliability evidence, risk signals, account context, and an explicit policy version. Only this engine returns `AUTO`, `VERIFY`, `HUMAN`, or `DENY`.

Hard invariants run before earned-autonomy thresholds. Examples include invalid values, over-refunds, fraud signals, custom contracts, high exposure, and missing current payment proof.

## Consequences

- Model confidence cannot bypass policy.
- Decisions are reproducible, versioned, testable, and suitable for an audit receipt.
- Prompt changes may alter proposals but cannot directly expand permission.
- Policy changes require code, tests, documentation, and a version comparison.

## Compliance evidence

Policy boundary tests cover high-confidence/high-risk cases, non-finite values, over-refunds, incomplete evidence, goodwill-credit handling, and policy-version differences.
