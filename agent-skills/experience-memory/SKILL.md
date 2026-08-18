---
name: experience-memory
description: Retrieve verified organizational experience with hybrid CockroachDB SQL and vector search. Use when an agent needs comparable episodes, failures, corrections, downstream outcomes, or task-specific reliability evidence before proposing an action.
---

# Experience Memory

Use structured filters for exact facts and vector search for semantic relevance.

## Workflow

1. Build a semantic representation from task type, request, contract, region, and value band.
2. Filter to the same task class and independently verified outcomes.
3. Retrieve nearest episodes and human correction lessons.
4. Aggregate success, failure, override, recency, and sample-size evidence.
5. Return evidence with provenance and similarity scores.

## Guardrails

- Similarity retrieves candidates; it never grants permission.
- Exclude pending and self-reported outcomes from reliability.
- Preserve policy version and verification quality for historical episodes.
- Surface low sample size and high novelty explicitly.
