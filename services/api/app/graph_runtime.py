from __future__ import annotations

import json
import time
from collections.abc import Iterator
from dataclasses import asdict
from typing import Any, Literal, TypeVar, TypedDict, cast

from langchain_core.runnables.config import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, StreamMode, interrupt

from .bedrock import SUPPORTED_ACTIONS
from .domain import AgentProposal, AgentRun, CustomerCase, DecisionMode
from .runtime import ReliabilityMemoryAgent
from .workflows import build_workflow_plan

T = TypeVar("T")


class AgentGraphRequiredState(TypedDict):
    thread_id: str
    request_id: str
    case: dict[str, Any]
    status: Literal["RUNNING", "AWAITING_HUMAN", "COMPLETED", "RESUMED"]


class AgentGraphState(AgentGraphRequiredState, total=False):
    """Serializable state shared by the one executable LangGraph node."""

    result: dict[str, Any]
    review_summary: dict[str, Any]
    correction_id: str
    human_resolution: dict[str, Any]


class ReliabilityGraphRuntime:
    """One-node LangGraph with typed state and durable human interrupts."""

    NODE_NAME = "reliability_memory_agent"

    def __init__(
        self,
        agent: ReliabilityMemoryAgent,
        checkpointer: BaseCheckpointSaver[Any] | None = None,
    ) -> None:
        self.agent = agent
        safe_serializer = JsonPlusSerializer(allowed_msgpack_modules=[])
        self.checkpointer = checkpointer or InMemorySaver(serde=safe_serializer)
        builder = StateGraph(AgentGraphState)
        builder.add_node(self.NODE_NAME, self._agent_node)
        builder.add_edge(START, self.NODE_NAME)
        builder.add_edge(self.NODE_NAME, END)
        self.graph = builder.compile(
            checkpointer=self.checkpointer,
            name="reliability-memory-one-node",
        )

    @property
    def executable_nodes(self) -> tuple[str, ...]:
        return (self.NODE_NAME,)

    def invoke(self, state: AgentGraphState) -> dict[str, Any]:
        output = cast(
            dict[str, Any],
            self.graph.invoke(cast(Any, state), self._config(state["thread_id"])),
        )
        return self._public_output(output, state["thread_id"])

    def resume(self, thread_id: str, resolution: dict[str, Any]) -> dict[str, Any]:
        output = cast(
            dict[str, Any],
            self.graph.invoke(
                Command(resume=resolution),
                self._config(thread_id),
            ),
        )
        return self._public_output(output, thread_id)

    def stream(
        self,
        state: AgentGraphState | None,
        *,
        thread_id: str,
        resolution: dict[str, Any] | None = None,
    ) -> Iterator[dict[str, Any]]:
        graph_input: AgentGraphState | Command[Any]
        graph_input = (
            Command(resume=resolution) if resolution is not None else cast(AgentGraphState, state)
        )
        yield {
            "type": "graph.started",
            "data": {
                "thread_id": thread_id,
                "executable_nodes": list(self.executable_nodes),
                "node_count": 1,
            },
        }
        stream_modes: list[StreamMode] = ["custom", "updates"]
        for mode, chunk in self.graph.stream(
            cast(Any, graph_input),
            self._config(thread_id),
            stream_mode=stream_modes,
        ):
            if mode == "custom":
                yield cast(dict[str, Any], chunk)
                continue
            if not isinstance(chunk, dict):
                continue
            interrupts = chunk.get("__interrupt__")
            if interrupts:
                review_payload = interrupts[0].value
                yield {"type": "review.required", "data": review_payload}
                yield {
                    "type": "graph.paused",
                    "data": {"thread_id": thread_id, "status": "AWAITING_HUMAN"},
                }
                continue
            node_update = chunk.get(self.NODE_NAME)
            if isinstance(node_update, dict):
                yield {
                    "type": "graph.completed",
                    "data": self._public_output(node_update, thread_id),
                }

    def _agent_node(self, state: AgentGraphState) -> AgentGraphState:
        writer = get_stream_writer()

        def emit(event: str, payload: dict[str, Any]) -> None:
            writer({"type": event, "data": _json_safe(payload)})

        case = CustomerCase(**state["case"])
        run = self.agent.run(case, state["request_id"], emit=emit)
        result = _json_safe(asdict(run))
        emit("run.result", result)

        if run.permission.mode not in {DecisionMode.HUMAN, DecisionMode.VERIFY}:
            return {
                **state,
                "status": "COMPLETED",
                "result": result,
            }

        summary = self._review_summary(run)
        self.agent.save_review_summary(run.run_id, summary)
        human_resolution = interrupt(
            {
                "thread_id": state["thread_id"],
                "episode_id": str(run.run_id),
                "result": result,
                "review_summary": summary,
            }
        )
        if not isinstance(human_resolution, dict):
            raise ValueError("Human resume payload must be an object")

        action, reason, lesson = self._resolve_human_action(run, summary, human_resolution)
        correction_id = self.agent.record_human_correction(
            run.run_id,
            action,
            reason,
            lesson,
        )
        emit(
            "review.resumed",
            {
                "episode_id": str(run.run_id),
                "correction_id": str(correction_id),
                "resolution": human_resolution.get("resolution", "approve_suggestion"),
            },
        )
        completed = self.agent.execute_reviewed_workflow(run, action, emit=emit)
        completed_result = _json_safe(asdict(completed))
        emit("run.result", completed_result)
        return {
            **state,
            "status": "RESUMED",
            "result": completed_result,
            "review_summary": summary,
            "human_resolution": cast(dict[str, Any], _json_safe(human_resolution)),
            "correction_id": str(correction_id),
        }

    @staticmethod
    def _review_summary(run: AgentRun) -> dict[str, Any]:
        if run.resolution_evidence is not None:
            suggested_action = {
                "action_type": run.resolution_evidence.recommended_action,
                "amount": run.resolution_evidence.recommended_amount,
            }
            default_reason = run.resolution_evidence.reason
            default_lesson = run.resolution_evidence.lesson
        else:
            suggested_action = {
                "action_type": run.proposal.action_type,
                "amount": run.proposal.amount,
            }
            default_reason = (
                "Reviewer confirmed the policy-gated proposal using the supplied evidence summary."
            )
            default_lesson = (
                "Reuse this reviewed resolution only in the same task, risk, and contract context."
            )

        review_proposal = AgentProposal(
            action_type=str(suggested_action["action_type"]),
            amount=cast(float, suggested_action["amount"]),
            reason=default_reason,
            checks_performed=("prefilled_human_review",),
        )
        review_workflow = build_workflow_plan(
            run.case,
            review_proposal,
            run.resolution_evidence,
        )

        return {
            "headline": f"Review {run.permission.mode.value.lower()} case for {run.case.customer_id}",
            "request": {
                "customer_id": run.case.customer_id,
                "task_type": run.case.task_type,
                "request_text": run.case.request_text,
                "requested_amount": run.case.requested_amount,
                "contract_type": run.case.contract_type,
            },
            "agent_recommendation": asdict(run.proposal),
            "evidence": {
                "reliability": run.evidence.reliability,
                "verified_cases": run.evidence.verified_cases,
                "failures": run.evidence.failures,
                "human_overrides": run.evidence.human_overrides,
                "relevant_corrections": run.evidence.relevant_corrections,
                "nearest_episode_ids": [
                    str(experience.episode_id) for experience in run.similar_experiences[:3]
                ],
                "mcp_verification": (
                    _json_safe(asdict(run.mcp_verification)) if run.mcp_verification else None
                ),
                "payment_evidence": (
                    asdict(run.payment_evidence) if run.payment_evidence else None
                ),
                "resolution_evidence": (
                    _json_safe(asdict(run.resolution_evidence)) if run.resolution_evidence else None
                ),
            },
            "policy": {
                "decision": run.permission.mode.value,
                "risk": run.permission.risk.value,
                "rule_id": run.permission.rule_id,
                "version": run.permission.policy_version,
                "reasons": list(run.permission.reasons),
            },
            "suggested_resolution": {
                **suggested_action,
                "reason": default_reason,
                "lesson": default_lesson,
            },
            "workflow_plan": _json_safe(asdict(review_workflow)),
            "reviewer_task": (
                "Confirm the pre-filled resolution and workflow, accept the proposal, or reject "
                "it. On approval, the agent executes the workflow; edit only fields that need "
                "correction."
            ),
        }

    @staticmethod
    def _resolve_human_action(
        run: AgentRun,
        summary: dict[str, Any],
        resolution: dict[str, Any],
    ) -> tuple[dict[str, Any], str, str]:
        choice = resolution.get("resolution", "approve_suggestion")
        suggested = cast(dict[str, Any], summary["suggested_resolution"])
        if choice == "reject":
            default_action: dict[str, Any] = {"action_type": "deny", "amount": 0.0}
        elif choice == "accept_proposal":
            default_action = {
                "action_type": run.proposal.action_type,
                "amount": run.proposal.amount,
            }
        elif choice == "approve_suggestion":
            default_action = {
                "action_type": suggested["action_type"],
                "amount": suggested["amount"],
            }
        else:
            raise ValueError(f"Unsupported human resolution: {choice}")

        action = {
            "action_type": resolution.get("action_type", default_action["action_type"]),
            "amount": round(float(resolution.get("amount", default_action["amount"])), 2),
        }
        if action["action_type"] not in SUPPORTED_ACTIONS:
            raise ValueError("Human action_type is invalid")
        if action["amount"] < 0 or action["amount"] > run.case.requested_amount:
            raise ValueError("Human resolution value violates the case invariant")
        reason = str(resolution.get("reason") or suggested["reason"]).strip()
        lesson = str(resolution.get("lesson") or suggested["lesson"]).strip()
        if len(reason) < 10 or len(lesson) < 10:
            raise ValueError("Human reason and lesson must each contain at least 10 characters")
        return action, reason, lesson

    @staticmethod
    def _config(thread_id: str) -> RunnableConfig:
        return {"configurable": {"thread_id": thread_id}}

    @staticmethod
    def _public_output(output: dict[str, Any], thread_id: str) -> dict[str, Any]:
        interrupts = output.get("__interrupt__")
        if interrupts:
            payload = interrupts[0].value
            return {
                "thread_id": thread_id,
                "status": "AWAITING_HUMAN",
                "result": payload["result"],
                "review_summary": payload["review_summary"],
            }
        return {
            "thread_id": thread_id,
            "status": output.get("status", "COMPLETED"),
            "result": output.get("result"),
            "review_summary": output.get("review_summary"),
            "correction_id": output.get("correction_id"),
            "human_resolution": output.get("human_resolution"),
        }


def build_checkpointer(database_url: str | None) -> BaseCheckpointSaver[Any]:
    safe_serializer = JsonPlusSerializer(allowed_msgpack_modules=[])
    if not database_url:
        return InMemorySaver(serde=safe_serializer)

    from langchain_cockroachdb import CockroachDBSaver
    from psycopg import Connection
    from psycopg.rows import dict_row

    connection = Connection.connect(
        database_url,
        autocommit=True,
        prepare_threshold=5,
        row_factory=dict_row,
    )
    saver = CockroachDBSaver(connection, serde=safe_serializer)
    _setup_cockroach_checkpointer(saver, connection)
    return cast(BaseCheckpointSaver[Any], saver)


def _setup_cockroach_checkpointer(saver: Any, connection: Any) -> None:
    """Initialize LangGraph tables safely across concurrent Lambda cold starts."""

    migrations = saver.MIGRATIONS
    connection.execute(migrations[0])
    expected_version = len(migrations) - 1

    for attempt in range(5):
        row = connection.execute(
            "SELECT v FROM checkpoint_migrations ORDER BY v DESC LIMIT 1"
        ).fetchone()
        current_version = -1 if row is None else int(row["v"])
        if current_version >= expected_version:
            return
        try:
            saver.setup()
            return
        except Exception as exc:
            if getattr(exc, "sqlstate", None) not in {"23505", "40001"} or attempt == 4:
                raise
            time.sleep(0.05 * (attempt + 1))

    raise RuntimeError("LangGraph checkpoint setup retry budget exhausted")


def _json_safe(value: T) -> T:
    return cast(T, json.loads(json.dumps(value, default=str)))
