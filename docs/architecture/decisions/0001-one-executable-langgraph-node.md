# ADR 0001: Use exactly one executable LangGraph node

> Status: Current (decision: Accepted)
>
> Audience: Architecture and backend contributors
>
> Owner: Reliability Memory maintainers
>
> Last reviewed: 2026-08-16

## Context

The project must demonstrate an agentic workflow through LangGraph while keeping the system understandable and avoiding a graph that merely renames ordinary function calls as nodes. Human review still needs durable interruption, checkpointing, streaming, and resume.

## Decision

Compile one executable node named `reliability_memory_agent` between the framework START and END sentinels. The state contract is the typed `AgentGraphState`. Customer context, experience memory, proposal, policy/risk, business action, verification, and learning remain skills invoked inside that node.

LangGraph provides:

- typed state propagation;
- custom and state-update streams;
- `interrupt()` for a prefilled human review;
- `Command(resume=...)` for continuation;
- an in-memory checkpointer locally and `CockroachDBSaver` in AWS.

## Consequences

- The graph topology is honest and can be asserted automatically.
- Skill sequencing remains explicit in normal Python code.
- A review resumes the same node, so every pre-interrupt side effect must be idempotent.
- If future domains require independently resumable branches, this decision must be revisited through a new ADR rather than adding nodes casually.

## Compliance evidence

`GET /health` returns `node_count: 1`, the only node name, and `typed_state: AgentGraphState`. Graph tests also inspect the executable node tuple and exercise interrupt/resume.
