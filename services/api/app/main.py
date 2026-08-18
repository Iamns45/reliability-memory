from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from collections.abc import Awaitable, Callable, Iterator
from dataclasses import asdict
from typing import Annotated, Any, Literal, TypeVar, cast
from uuid import UUID, uuid4

from fastapi import FastAPI, Header, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .bedrock import (
    BedrockReasoner,
    DeterministicDemoReasoner,
    DeterministicEmbeddingProvider,
    TitanEmbeddingProvider,
)
from .domain import CustomerCase
from .graph_runtime import AgentGraphState, ReliabilityGraphRuntime, build_checkpointer
from .mcp_memory import (
    CockroachCloudMcpGateway,
    DisabledMcpVerifier,
    McpMemoryVerifier,
    McpVerifier,
)
from .repository import (
    CockroachMemoryRepository,
    EpisodeNotReviewableError,
    InMemoryMemoryRepository,
)
from .runtime import ReliabilityMemoryAgent
from .settings import Settings

LOGGER = logging.getLogger("reliability_memory.api")
LOGGER.setLevel(logging.INFO)
IDEMPOTENCY_KEY_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$"
T = TypeVar("T")


class CustomerCaseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    case_id: str | None = Field(
        default=None,
        min_length=8,
        max_length=80,
        pattern=r"^CASE-[A-Za-z0-9-]+$",
    )
    customer_id: str = Field(min_length=2, max_length=80, pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]+$")
    task_type: str = Field(
        default="general_customer_resolution",
        min_length=2,
        max_length=80,
        pattern=r"^[a-z][a-z0-9_]+$",
    )
    request_text: str = Field(min_length=5, max_length=4000)
    requested_amount: float = Field(gt=0, le=1_000_000)
    account_type: Literal["standard", "premium", "enterprise", "education"] = "standard"
    region: str = Field(default="US", min_length=2, max_length=20)
    contract_type: str = Field(default="standard", min_length=2, max_length=50)
    fraud_signal: bool = False
    existing_credit: float = Field(default=0, ge=0)
    ground_truth_amount: float | None = Field(default=None, ge=0)
    memory_enabled: bool = True

    @model_validator(mode="after")
    def validate_amounts(self) -> "CustomerCaseRequest":
        if self.existing_credit > self.requested_amount:
            raise ValueError("existing_credit cannot exceed requested_amount")
        if (
            self.ground_truth_amount is not None
            and self.ground_truth_amount > self.requested_amount
        ):
            raise ValueError("ground_truth_amount cannot exceed requested_amount")
        return self


class HumanCorrectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    run_id: UUID
    action_type: Literal[
        "cost_containment",
        "database_capacity_recovery",
        "deny",
        "exchange",
        "guided_troubleshooting",
        "isolated_restore",
        "least_privilege_fix",
        "partial_refund",
        "quota_adjustment",
        "refund",
        "replacement",
        "reship",
        "rollback_deployment",
        "safety_escalation",
        "seller_investigation",
        "security_containment",
        "ship_missing_part",
        "store_credit",
        "traffic_stabilization",
        "warranty_repair",
    ]
    amount: float = Field(ge=0, le=1_000_000)
    reason: str = Field(min_length=10, max_length=1_000)
    lesson: str = Field(min_length=10, max_length=2_000)


class HumanResumeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    resolution: Literal["approve_suggestion", "accept_proposal", "reject"] = "approve_suggestion"
    action_type: (
        Literal[
            "cost_containment",
            "database_capacity_recovery",
            "deny",
            "exchange",
            "guided_troubleshooting",
            "isolated_restore",
            "least_privilege_fix",
            "partial_refund",
            "quota_adjustment",
            "refund",
            "replacement",
            "reship",
            "rollback_deployment",
            "safety_escalation",
            "seller_investigation",
            "security_containment",
            "ship_missing_part",
            "store_credit",
            "traffic_stabilization",
            "warranty_repair",
        ]
        | None
    ) = None
    amount: float | None = Field(default=None, ge=0, le=1_000_000)
    reason: str | None = Field(default=None, min_length=10, max_length=1_000)
    lesson: str | None = Field(default=None, min_length=10, max_length=2_000)


class DelayedOutcomeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    run_id: UUID
    task_type: str = Field(min_length=2, max_length=80, pattern=r"^[a-z][a-z0-9_]+$")
    success: bool
    reason: str = Field(min_length=10, max_length=1_000)


class EvidenceFaultRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    case_id: str = Field(
        min_length=8,
        max_length=80,
        pattern=r"^CASE-[A-Za-z0-9-]+$",
    )
    fault_type: Literal["corrupt_hash", "stale_record", "mismatch_correlation"]
    source_key: str | None = Field(default=None, min_length=2, max_length=80)


def create_app(settings: Settings | None = None) -> FastAPI:
    runtime_settings = settings or Settings.from_environment()
    agent = _build_agent(runtime_settings)
    graph_runtime = ReliabilityGraphRuntime(
        agent,
        build_checkpointer(runtime_settings.database_url),
    )
    application = FastAPI(
        title="Reliability Memory Resolution Operations API",
        version="1.3.0",
        description=(
            "One-node typed LangGraph for evidence-specific consumer and enterprise operations, "
            "strict evidence admission, deterministic permission, streamed execution, containment "
            "proof, and durable human interrupt/resume."
        ),
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(runtime_settings.cors_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=[
            "Accept",
            "Cache-Control",
            "Content-Type",
            "Idempotency-Key",
            "X-Request-Id",
        ],
    )

    @application.middleware("http")
    async def request_observability(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = request.headers.get("x-request-id") or str(uuid4())
        started_at = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-Id"] = request_id
            return response
        finally:
            LOGGER.info(
                json.dumps(
                    {
                        "event": "http_request",
                        "request_id": request_id,
                        "method": request.method,
                        "path": request.url.path,
                        "status": status_code,
                        "duration_ms": round((time.perf_counter() - started_at) * 1000, 2),
                    }
                )
            )

    @application.get("/health", operation_id="getHealth", tags=["operations"])
    def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "memory": "cockroachdb" if runtime_settings.database_url else "credential-free demo",
            "model": "amazon-bedrock" if runtime_settings.use_bedrock else "deterministic demo",
            "model_id": (
                runtime_settings.bedrock_model_id
                if runtime_settings.use_bedrock
                else "deterministic-demo-reasoner"
            ),
            "policy": "customer-resolution-v5.0",
            "cockroachdb_tools": [
                "distributed-vector-indexing",
                *(["cloud-managed-mcp"] if runtime_settings.mcp_configured else []),
            ],
            "mcp": {
                "status": "configured" if runtime_settings.mcp_configured else "disabled",
                "provider": "cockroachdb-cloud-managed-mcp",
                "endpoint": runtime_settings.mcp_endpoint,
                "cluster_scope": (
                    f"{runtime_settings.mcp_cluster_id[:8]}…"
                    if runtime_settings.mcp_cluster_id
                    else None
                ),
                "database": runtime_settings.mcp_database,
                "required_for_autonomy": runtime_settings.mcp_required,
                "read_only": True,
                "verification_checks": ["persisted-episode", "vector-neighbor-overlap"],
            },
            "graph": {
                "framework": "langgraph",
                "node_count": 1,
                "nodes": list(graph_runtime.executable_nodes),
                "typed_state": "AgentGraphState",
                "checkpointer": (
                    "cockroachdb" if runtime_settings.database_url else "in-memory-demo"
                ),
            },
        }

    @application.post("/v1/cases/run", operation_id="runCustomerCase", tags=["agent"])
    def run_case(
        payload: CustomerCaseRequest,
        idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    ) -> dict[str, Any]:
        _validate_idempotency_key(idempotency_key)
        state = _graph_state(payload, idempotency_key, agent)
        return graph_runtime.invoke(state)

    @application.post("/v1/cases/stream", operation_id="streamCustomerCase", tags=["agent"])
    def stream_case(
        payload: CustomerCaseRequest,
        idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    ) -> StreamingResponse:
        _validate_idempotency_key(idempotency_key)
        state = _graph_state(payload, idempotency_key, agent)
        return _event_stream(
            graph_runtime.stream(state, thread_id=state["thread_id"]),
        )

    @application.post(
        "/v1/cases/{thread_id}/resume",
        operation_id="resumeCustomerCase",
        tags=["agent"],
    )
    def resume_case(thread_id: str, payload: HumanResumeRequest) -> dict[str, Any]:
        _validate_idempotency_key(thread_id)
        try:
            return graph_runtime.resume(thread_id, payload.model_dump(exclude_none=True))
        except EpisodeNotReviewableError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @application.post(
        "/v1/cases/{thread_id}/resume/stream",
        operation_id="streamResumeCustomerCase",
        tags=["agent"],
    )
    def stream_resume_case(
        thread_id: str,
        payload: HumanResumeRequest,
    ) -> StreamingResponse:
        _validate_idempotency_key(thread_id)
        return _event_stream(
            graph_runtime.stream(
                None,
                thread_id=thread_id,
                resolution=payload.model_dump(exclude_none=True),
            )
        )

    @application.post(
        "/v1/corrections",
        operation_id="recordHumanCorrection",
        tags=["agent"],
        status_code=201,
    )
    def record_human_correction(payload: HumanCorrectionRequest) -> dict[str, str]:
        try:
            correction_id = agent.record_human_correction(
                episode_id=payload.run_id,
                human_action={
                    "action_type": payload.action_type,
                    "amount": round(payload.amount, 2),
                },
                reason=payload.reason,
                lesson=payload.lesson,
            )
        except EpisodeNotReviewableError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {
            "status": "stored",
            "run_id": str(payload.run_id),
            "correction_id": str(correction_id),
        }

    @application.get(
        "/v1/cases/catalog",
        operation_id="listAnalystCases",
        tags=["agent"],
    )
    def list_analyst_cases() -> dict[str, Any]:
        records = agent.list_analyst_cases()
        return {
            "source": ("cockroachdb" if runtime_settings.database_url else "credential-free-demo"),
            "count": len(records),
            "cases": _json_safe(records),
        }

    @application.get(
        "/v1/receipts/{run_id}",
        operation_id="getEvidenceReceipt",
        tags=["evidence"],
    )
    def get_evidence_receipt(run_id: UUID) -> dict[str, Any]:
        try:
            receipt = _json_safe(agent.evidence_receipt(run_id))
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Episode not found") from exc
        canonical = json.dumps(receipt, sort_keys=True, separators=(",", ":"))
        return {
            "receipt_version": "evidence-receipt-v2",
            "episode_id": str(run_id),
            "sha256": hashlib.sha256(canonical.encode()).hexdigest(),
            "record": receipt,
        }

    @application.get(
        "/v1/reliability/envelope",
        operation_id="getReliabilityEnvelope",
        tags=["evidence"],
    )
    def get_reliability_envelope() -> dict[str, Any]:
        return {
            "policy_version": "customer-resolution-v5.0",
            "contexts": _json_safe(agent.reliability_envelope()),
        }

    @application.get(
        "/v1/reliability/autonomy-ledger",
        operation_id="getAutonomyLedger",
        tags=["evidence"],
    )
    def get_autonomy_ledger() -> dict[str, Any]:
        return _json_safe(agent.autonomy_ledger())

    @application.get(
        "/v1/impact/summary",
        operation_id="getImpactSummary",
        tags=["evidence"],
    )
    def get_impact_summary() -> dict[str, Any]:
        return _json_safe(agent.impact_summary())

    @application.post(
        "/v1/experiments/memory-ablation",
        operation_id="compareMemoryAblation",
        tags=["experiments"],
    )
    def compare_memory(payload: CustomerCaseRequest) -> dict[str, Any]:
        return _json_safe(agent.compare_memory(_case_from_payload(payload, agent)))

    @application.post(
        "/v1/experiments/policy-comparison",
        operation_id="comparePolicyVersions",
        tags=["experiments"],
    )
    def compare_policy(payload: CustomerCaseRequest) -> dict[str, Any]:
        return _json_safe(agent.compare_policies(_case_from_payload(payload, agent)))

    @application.post(
        "/v1/experiments/idempotency",
        operation_id="injectRepeatedRequest",
        tags=["experiments"],
    )
    def inject_repeated_request(payload: CustomerCaseRequest) -> dict[str, Any]:
        request_id = f"failure-injection-{uuid4()}"
        case = _case_from_payload(payload, agent)
        first = agent.run(case, request_id)
        second = agent.run(case, request_id)
        return _json_safe(
            {
                "injection": "repeated_request",
                "idempotency_key": request_id,
                "first_episode_id": first.run_id,
                "second_episode_id": second.run_id,
                "same_episode": first.run_id == second.run_id,
                "first_provider_reference": (
                    first.execution.provider_reference if first.execution else None
                ),
                "second_provider_reference": (
                    second.execution.provider_reference if second.execution else None
                ),
                "repeat_action_prevented": (
                    first.execution is not None
                    and second.execution is None
                    and second.idempotency_reused
                ),
            }
        )

    @application.post(
        "/v1/experiments/evidence-fault",
        operation_id="simulateEvidenceFault",
        tags=["experiments"],
    )
    def simulate_evidence_fault(payload: EvidenceFaultRequest) -> dict[str, Any]:
        record = agent.get_analyst_case(payload.case_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Analyst case not found")
        try:
            return _json_safe(
                agent.simulate_evidence_fault(
                    _case_from_record(record),
                    payload.fault_type,
                    payload.source_key,
                )
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @application.post(
        "/v1/outcomes/delayed",
        operation_id="recordDelayedOutcome",
        tags=["evidence"],
        status_code=201,
    )
    def record_delayed_outcome(payload: DelayedOutcomeRequest) -> dict[str, Any]:
        try:
            result = agent.record_delayed_outcome(
                payload.run_id,
                payload.task_type,
                payload.success,
                payload.reason,
            )
        except EpisodeNotReviewableError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return _json_safe(result)

    return application


def _build_agent(settings: Settings) -> ReliabilityMemoryAgent:
    repository = (
        CockroachMemoryRepository(settings.database_url)
        if settings.database_url
        else InMemoryMemoryRepository()
    )
    reasoner = (
        BedrockReasoner(region=settings.aws_region, model_id=settings.bedrock_model_id)
        if settings.use_bedrock
        else DeterministicDemoReasoner()
    )
    embeddings = (
        TitanEmbeddingProvider(region=settings.aws_region)
        if settings.use_bedrock
        else DeterministicEmbeddingProvider()
    )
    mcp_verifier: McpVerifier
    if settings.mcp_configured:
        assert settings.mcp_api_key is not None
        assert settings.mcp_cluster_id is not None
        mcp_verifier = McpMemoryVerifier(
            CockroachCloudMcpGateway(
                endpoint=settings.mcp_endpoint,
                api_key=settings.mcp_api_key,
                cluster_id=settings.mcp_cluster_id,
                database=settings.mcp_database,
                timeout_seconds=settings.mcp_timeout_seconds,
            ),
            required=settings.mcp_required,
        )
    else:
        mcp_verifier = DisabledMcpVerifier()
    return ReliabilityMemoryAgent(repository, reasoner, embeddings, mcp_verifier=mcp_verifier)


def _graph_state(
    payload: CustomerCaseRequest,
    idempotency_key: str,
    agent: ReliabilityMemoryAgent,
) -> AgentGraphState:
    return {
        "thread_id": idempotency_key,
        "request_id": idempotency_key,
        "case": asdict(_case_from_payload(payload, agent)),
        "status": "RUNNING",
    }


def _case_from_payload(
    payload: CustomerCaseRequest,
    agent: ReliabilityMemoryAgent,
) -> CustomerCase:
    if payload.case_id is not None:
        record = agent.get_analyst_case(payload.case_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Analyst case not found")
        return _case_from_record(record, memory_enabled=payload.memory_enabled)
    return CustomerCase(
        customer_id=payload.customer_id,
        task_type=payload.task_type,
        request_text=payload.request_text,
        requested_amount=payload.requested_amount,
        account_type=payload.account_type,
        region=payload.region,
        contract_type=payload.contract_type,
        fraud_signal=payload.fraud_signal,
        existing_credit=payload.existing_credit,
        memory_enabled=payload.memory_enabled,
        metadata=(
            {"ground_truth_amount": payload.ground_truth_amount}
            if payload.ground_truth_amount is not None
            else {}
        ),
    )


def _case_from_record(
    record: dict[str, Any],
    *,
    memory_enabled: bool = True,
) -> CustomerCase:
    customer = cast(dict[str, Any], record["customer"])
    ground_truth = record.get("ground_truth_amount")
    return CustomerCase(
        customer_id=str(customer["customer_id"]),
        task_type=str(record["task_type"]),
        request_text=str(record["request_text"]),
        requested_amount=float(record["requested_amount"]),
        account_type=str(customer["account_type"]),
        region=str(customer["region"]),
        contract_type=str(customer["contract_type"]),
        fraud_signal=bool(record["fraud_signal"]),
        existing_credit=float(record["existing_credit"]),
        memory_enabled=memory_enabled,
        metadata={
            "case_id": str(record["case_id"]),
            "case_evidence": {
                "issue_type": record["task_type"],
                "customer_segment": record.get("customer_segment", "consumer"),
                "evidence_as_of": record.get("evidence_as_of"),
                "customer_goal": record.get("customer_goal"),
                "business_guardrail": record.get("business_guardrail"),
                "evidence_required": record.get("evidence_required", []),
                "evidence_sources": record.get("evidence_sources", []),
                "resolution_options": record.get("resolution_options", []),
                "resolution_constraints": record.get("resolution_constraints", {}),
            },
            **({"ground_truth_amount": float(ground_truth)} if ground_truth is not None else {}),
        },
    )


def _event_stream(events: Iterator[dict[str, Any]]) -> StreamingResponse:
    def encoded() -> Iterator[str]:
        for event in events:
            event_type = str(event.get("type", "message")).replace("\n", "")
            yield f"event: {event_type}\ndata: {json.dumps(event, default=str)}\n\n"

    return StreamingResponse(
        encoded(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _validate_idempotency_key(value: str) -> None:
    if not re.fullmatch(IDEMPOTENCY_KEY_PATTERN, value):
        raise HTTPException(
            status_code=400,
            detail=(
                "Idempotency-Key must contain 8–128 letters, numbers, periods, colons, "
                "underscores, or hyphens"
            ),
        )


def _json_safe(value: T) -> T:
    return cast(T, json.loads(json.dumps(value, default=str)))


app = create_app()
