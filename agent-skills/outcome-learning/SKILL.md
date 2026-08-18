---
name: outcome-learning
description: Verify executed outcomes and write durable experience or human corrections. Use after a business action, approval, rejection, or correction so future reliability is based only on independently checked evidence.
---

# Outcome Learning

Close the loop from action to verified organizational experience.

## Workflow

1. Compare the executed action with independent task-specific ground truth.
2. Record immediate success or failure without asking the agent to self-grade.
3. When a reviewer intervenes, preserve proposal, resolved action, reason, and reusable lesson.
4. Atomically attach the outcome or correction to its episode.
5. Schedule delayed checks for reopen, chargeback, complaint, or retention signals.

## Guardrails

- Pending outcomes do not affect reliability.
- Human corrections count as overrides, not agent successes.
- Make episode completion idempotent.
- Retain policy version and verifier identity for auditability.
