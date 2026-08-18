# ADR 0005: Use issue-specific evidence and resolution economics

> Status: Accepted
>
> Date: 2026-08-16
>
> Decision owners: Product, backend, and policy maintainers

## Context

A refund amount and customer history do not establish what happened. Damage, delivery, device failure, missing components, safety, identity, seller integrity, and service recovery require different authoritative facts and actions. One generic checklist produces vague decisions and unnecessary customer or company loss.

## Decision

Each `analyst_cases` row stores a versionable `evidence_bundle` describing required sources, source facts, customer goal, business guardrail, feasible options, customer value, company cost, and an evidence-derived bounded resolution.

The runtime converts the bundle to typed `ResolutionEvidence`. Policy v5.0 requires source completeness and proposal-plan agreement before reliability can affect permission. Safety, human, verify, and deny floors remain deterministic. Historical behavior is contextual evidence and cannot by itself prove abuse.

## Consequences

- Adding a new issue requires a source contract and tested policy boundary.
- The UI can explain why the selected action is better than its alternatives.
- Product-quality, carrier, warehouse, seller, and device signals become visible to analysts.
- Evidence bundles must be governed and versioned when used with real integrations.
- The legacy amount-first policy remains only as an explicit comparison baseline.

## Verification

Catalog tests require task diversity, source completeness, action diversity, and economics. Runtime tests cover automatic replacement, human safety or exception boundaries, correction replay, and authoritative catalog reloads.
