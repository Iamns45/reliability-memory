import type { DemoCase } from "./demo-data";

const HEALTH_TIMEOUT_MS = 5_000;
const RUN_TIMEOUT_MS = 65_000;

export type RuntimeState = "checking" | "live" | "preview" | "error";
export type DecisionMode = "AUTO" | "VERIFY" | "HUMAN" | "DENY";
export type RiskLevel = "LOW" | "MEDIUM" | "HIGH";

export type WorkflowPlan = {
  workflow_type: string;
  name: string;
  objective: string;
  steps: Array<{
    step_id: string;
    title: string;
    system: string;
    operation: string;
    detail: string;
    reversible: boolean;
  }>;
  compensation: string;
};

export type RuntimeHealth = {
  status: "ok";
  memory: string;
  model: string;
  model_id: string;
  policy: string;
  cockroachdb_tools: string[];
  mcp: {
    status: "configured" | "disabled";
    provider: string;
    endpoint: string;
    cluster_scope: string | null;
    database: string;
    required_for_autonomy: boolean;
    read_only: boolean;
    verification_checks: string[];
  };
  graph: {
    framework: "langgraph";
    node_count: 1;
    nodes: string[];
    typed_state: string;
    checkpointer: string;
  };
};

export type AgentRunResponse = {
  run_id: string;
  case: {
    customer_id: string;
    task_type: string;
    request_text: string;
    requested_amount: number;
    account_type: string;
    region: string;
    contract_type: string;
    fraud_signal: boolean;
    existing_credit: number;
    memory_enabled: boolean;
    metadata: Record<string, unknown>;
  };
  proposal: {
    action_type: string;
    amount: number;
    reason: string;
    confidence: number | null;
    checks_performed: string[];
  };
  evidence: {
    reliability: number;
    verified_cases: number;
    successes: number;
    failures: number;
    human_overrides: number;
    average_similarity: number;
    evidence_quality: string;
    novelty: string;
    relevant_corrections: number;
    memory_enabled: boolean;
    last_verified_at: string | null;
  };
  permission: {
    mode: DecisionMode;
    risk: RiskLevel;
    policy_version: string;
    reasons: string[];
    rule_id: string;
  };
  counterfactual?: {
    target_mode: "AUTO";
    attainable: boolean;
    validated_by_policy: boolean;
    resulting_mode: DecisionMode;
    requirements: Array<{
      signal: string;
      current: string;
      required: string;
      delta: string;
      rationale: string;
    }>;
    hard_boundaries: string[];
    summary: string;
  };
  similar_experiences: Array<{
    episode_id: string;
    summary: string;
    similarity: number;
    verified_success: boolean;
    correction_lesson: string | null;
  }>;
  payment_evidence: null | {
    duplicate_confirmed: boolean;
    checked_payments: number;
    original_payment_id: string | null;
    duplicate_payment_id: string | null;
    amount: number | null;
    currency: string | null;
    subscription_reference: string | null;
    capture_gap_seconds: number | null;
    matched_on: string[];
    safeguards: string[];
    blocking_reasons: string[];
  };
  resolution_evidence: null | {
    issue_type: string;
    evidence_complete: boolean;
    autonomy_eligible: boolean;
    evidence_grade: "EXACT" | "REVIEW" | "BLOCKED";
    evidence_as_of: string;
    required_sources: string[];
    completed_sources: string[];
    source_checks: Array<{
      key: string;
      label: string;
      status: string;
      summary: string;
      facts: string[];
      authority: string;
      source_system: string;
      source_record_id: string;
      integrity: string;
      integrity_hash: string;
      observed_at: string;
      max_age_seconds: number;
      conflicts: string[];
      correlation: {
        case_id: string;
        customer_id: string;
        task_type: string;
      };
      freshness_status: string;
      admissible: boolean;
      admissibility_reasons: string[];
    }>;
    recommended_action: string;
    recommended_amount: number;
    company_cost: number;
    customer_value: number;
    permission_floor: DecisionMode;
    auto_cost_cap: number;
    safety_critical: boolean;
    customer_goal: string;
    business_guardrail: string;
    positive_facts: string[];
    blocking_reasons: string[];
    alternatives: Array<{
      action: string;
      amount: number;
      customer_value: number;
      company_cost: number;
      goal_fit: number;
      eligible: boolean;
      permission_floor: DecisionMode;
      selection_score: number;
      selection_eligible: boolean;
      selection_exclusions: string[];
      selected: boolean;
      value_components: Array<{
        label: string;
        amount: number;
        basis: string;
      }>;
      label: string;
    }>;
    selection_method: string;
    selection_score: number;
    selection_rationale: string;
    eligible_option_count: number;
    value_components: Array<{
      label: string;
      amount: number;
      basis: string;
    }>;
    reason: string;
    lesson: string;
  };
  workflow_plan: WorkflowPlan;
  containment: {
    status: string;
    level: "L2_AUTONOMOUS" | "L3_SUPERVISED";
    root_cause: string;
    evidence_grade: "EXACT" | "REVIEW" | "BLOCKED";
    evidence_record_ids: string[];
    required_evidence_count: number;
    admissible_evidence_count: number;
    decision_rule: string;
    workflow_id: string | null;
    executed_operations: number;
    verified: boolean;
    human_minutes_avoided: number;
    estimated_company_cost: number;
    customer_value: number;
    reopen_monitor_until: string;
  };
  execution: null | {
    action_id: string;
    idempotency_key: string;
    executed_amount: number;
    status: string;
    provider_reference: string;
    workflow_id: string;
    workflow_name: string;
    steps: Array<{
      step_id: string;
      status: string;
      provider_reference: string;
      detail: string;
    }>;
    artifacts: Record<string, string>;
  };
  verification: null | {
    success: boolean;
    expected_amount: number;
    actual_amount: number;
    reason: string;
  };
  mcp_verification: null | {
    provider: string;
    endpoint: string;
    cluster_scope: string;
    database: string;
    tool_name: string;
    required: boolean;
    verified: boolean;
    episode_id: string;
    observed_episode_id: string | null;
    observed_decision: string | null;
    observed_policy_version: string | null;
    vector_check_performed: boolean;
    expected_neighbor_ids: string[];
    vector_neighbor_ids: string[];
    matching_neighbor_ids: string[];
    checked_at: string;
    receipt_hash: string;
    failure_reason: string | null;
  };
  created_at: string;
  idempotency_reused: boolean;
};

export type ReviewSummary = {
  headline: string;
  request: Record<string, unknown>;
  agent_recommendation: AgentRunResponse["proposal"];
  evidence: {
    reliability: number;
    verified_cases: number;
    failures: number;
    human_overrides: number;
    relevant_corrections: number;
    nearest_episode_ids: string[];
    mcp_verification: AgentRunResponse["mcp_verification"];
    payment_evidence: AgentRunResponse["payment_evidence"];
    resolution_evidence: AgentRunResponse["resolution_evidence"];
  };
  policy: {
    decision: DecisionMode;
    risk: RiskLevel;
    rule_id: string;
    version: string;
    reasons: string[];
  };
  suggested_resolution: {
    action_type: string;
    amount: number;
    reason: string;
    lesson: string;
  };
  workflow_plan: WorkflowPlan;
  reviewer_task: string;
};

export type GraphRunResponse = {
  thread_id: string;
  status: "AWAITING_HUMAN" | "COMPLETED" | "RESUMED";
  result: AgentRunResponse;
  review_summary?: ReviewSummary | null;
  correction_id?: string | null;
};

export type StreamEvent = {
  type: string;
  data: Record<string, unknown>;
};

export type AnalystCaseRecord = {
  case_id: string;
  title: string;
  queue_status: string;
  priority: string;
  task_type: string;
  request_text: string;
  requested_amount: number;
  existing_credit: number;
  fraud_signal: boolean;
  ground_truth_amount: number | null;
  expected_mode: DecisionMode;
  customer_segment: "consumer" | "enterprise";
  evidence_as_of: string;
  customer_goal: string;
  business_guardrail: string;
  evidence_required: string[];
  evidence_sources: Array<{
    key: string;
    label: string;
    status: string;
    summary: string;
    facts: string[];
    authority: string;
    source_system: string;
    source_record_id: string;
    integrity: string;
    integrity_hash: string;
    observed_at: string;
    max_age_seconds: number;
    conflicts: string[];
    correlation: {
      case_id: string;
      customer_id: string;
      task_type: string;
    };
  }>;
  resolution_options: Array<{
    action: string;
    amount: number;
    customer_value: number;
    company_cost: number;
    goal_fit: number;
    eligible: boolean;
    permission_floor: DecisionMode;
    auto_cost_cap: number;
    safety_critical: boolean;
    selection_score?: number;
    selection_eligible?: boolean;
    selection_exclusions?: string[];
    selected?: boolean;
    value_components: Array<{
      label: string;
      amount: number;
      basis: string;
    }>;
    label: string;
  }>;
  resolution_constraints: {
    default_permission_floor: DecisionMode;
    auto_cost_cap: number;
    safety_critical: boolean;
    resolution_cost_cap: number;
    minimum_goal_fit: number;
  };
  created_at?: string;
  customer: {
    customer_id: string;
    display_name: string;
    account_type: string;
    region: string;
    contract_type: string;
  };
  events: Array<{
    event_type: string;
    event_at: string;
    data: Record<string, unknown>;
  }>;
  payments: Array<{
    payment_id: string;
    provider: string;
    merchant_reference: string;
    subscription_reference: string;
    billing_period: string;
    payment_method_fingerprint: string;
    amount: number;
    currency: string;
    status: string;
    captured_at: string;
    refunded: boolean;
    reversed: boolean;
    disputed: boolean;
  }>;
};

export type EnvelopeRow = {
  context: string;
  task_type: string;
  constraints: Record<string, unknown>;
  evidence: AgentRunResponse["evidence"];
  permission: AgentRunResponse["permission"];
};

export type ImpactSummary = {
  currency: "USD";
  verified_outcomes: number;
  successful_outcomes: number;
  task_contexts: number;
  customer_value_delivered: number;
  evidence_selected_company_cost: number;
  refund_first_baseline_cost: number;
  estimated_cost_avoided: number;
  methodology: string;
};

export type AutonomyLedger = {
  ledger_version: string;
  policy_version: string;
  entry_count: number;
  head_hash: string;
  entries: Array<{
    sequence: number;
    effective_at: string;
    task_type: string;
    context: string;
    event: "AUTONOMY_EARNED" | "AUTONOMY_WITHHELD";
    mode: DecisionMode;
    rule_id: string;
    policy_version: string;
    verified_cases: number;
    reliability: number;
    previous_hash: string;
    entry_hash: string;
  }>;
};

export function expectsAwsRuntime(): boolean {
  if (typeof document === "undefined") return false;
  const localHost = new Set(["localhost", "127.0.0.1", "::1"]);
  return document.body.dataset.deployment === "aws" && !localHost.has(window.location.hostname);
}

export async function fetchRuntimeHealth(signal?: AbortSignal): Promise<RuntimeHealth> {
  return fetchJson<RuntimeHealth>(
    "/health",
    {
      headers: { Accept: "application/json" },
      signal,
      timeoutMs: HEALTH_TIMEOUT_MS,
    },
    "Runtime health check failed",
  );
}

export async function runDemoCase(
  demoCase: DemoCase,
  learned: boolean,
  memoryEnabled: boolean,
  onEvent: (event: StreamEvent) => void,
): Promise<GraphRunResponse> {
  const idempotencyKey = `judge-${demoCase.id}-${crypto.randomUUID()}`;
  return consumeGraphStream(
    "/v1/cases/stream",
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": idempotencyKey,
      },
      body: JSON.stringify(buildCasePayload(demoCase, learned, memoryEnabled)),
    },
    onEvent,
  );
}

export async function resumeHumanReview(
  threadId: string,
  onEvent: (event: StreamEvent) => void,
): Promise<GraphRunResponse> {
  return consumeGraphStream(
    `/v1/cases/${encodeURIComponent(threadId)}/resume/stream`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ resolution: "approve_suggestion" }),
    },
    onEvent,
  );
}

export async function fetchEnvelope(): Promise<EnvelopeRow[]> {
  const response = await fetchJson<{ contexts: EnvelopeRow[] }>(
    "/v1/reliability/envelope",
    { timeoutMs: HEALTH_TIMEOUT_MS },
    "Reliability envelope failed",
  );
  return response.contexts;
}

export async function fetchImpactSummary(): Promise<ImpactSummary> {
  return fetchJson<ImpactSummary>(
    "/v1/impact/summary",
    { timeoutMs: RUN_TIMEOUT_MS },
    "Impact summary failed",
  );
}

export async function fetchAutonomyLedger(): Promise<AutonomyLedger> {
  return fetchJson<AutonomyLedger>(
    "/v1/reliability/autonomy-ledger",
    { timeoutMs: RUN_TIMEOUT_MS },
    "Autonomy ledger failed",
  );
}

export async function fetchAnalystCases(): Promise<AnalystCaseRecord[]> {
  const response = await fetchJson<{ cases: AnalystCaseRecord[] }>(
    "/v1/cases/catalog",
    { timeoutMs: HEALTH_TIMEOUT_MS },
    "Analyst case catalog failed",
  );
  return response.cases;
}

export async function runMemoryAblation(demoCase: DemoCase, learned: boolean): Promise<unknown> {
  return postExperiment(
    "/v1/experiments/memory-ablation",
    buildCasePayload(demoCase, learned, true),
  );
}

export async function comparePolicyVersions(
  demoCase: DemoCase,
  learned: boolean,
): Promise<unknown> {
  return postExperiment(
    "/v1/experiments/policy-comparison",
    buildCasePayload(demoCase, learned, true),
  );
}

export async function injectRepeatedRequest(demoCase: DemoCase): Promise<unknown> {
  return postExperiment("/v1/experiments/idempotency", buildCasePayload(demoCase, false, true));
}

export async function simulateEvidenceFault(
  caseId: string,
  faultType: "corrupt_hash" | "stale_record" | "mismatch_correlation",
): Promise<unknown> {
  return postExperiment("/v1/experiments/evidence-fault", {
    case_id: caseId,
    fault_type: faultType,
  });
}

export async function simulateDelayedOutcome(run: AgentRunResponse): Promise<unknown> {
  return postExperiment("/v1/outcomes/delayed", {
    run_id: run.run_id,
    task_type: run.case.task_type,
    success: false,
    reason: "A simulated later customer or provider outcome invalidated the immediate resolution.",
  });
}

export async function downloadEvidenceReceipt(runId: string): Promise<void> {
  const receipt = await fetchJson<Record<string, unknown>>(
    `/v1/receipts/${encodeURIComponent(runId)}`,
    { timeoutMs: HEALTH_TIMEOUT_MS },
    "Evidence receipt failed",
  );
  const blob = new Blob([JSON.stringify(receipt, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `evidence-receipt-${runId}.json`;
  link.click();
  URL.revokeObjectURL(url);
}

function buildCasePayload(
  demoCase: DemoCase,
  learned: boolean,
  memoryEnabled: boolean,
): Record<string, unknown> {
  const learnedCase = learned ? demoCase.learned : undefined;
  const [accountType, region = "US"] = demoCase.account.split(" · ");
  return {
    case_id: learnedCase?.nextCaseId ?? demoCase.caseId,
    customer_id: learnedCase?.nextCustomerId ?? demoCase.customerId,
    task_type: demoCase.taskType,
    request_text: learnedCase?.nextRequest ?? demoCase.request,
    requested_amount: learnedCase?.nextAmount ?? demoCase.amount,
    account_type: accountType.toLowerCase(),
    region,
    contract_type: demoCase.contractType,
    fraud_signal: demoCase.fraudSignal ?? false,
    existing_credit: demoCase.existingCredit ?? 0,
    ground_truth_amount:
      learnedCase?.nextProposedAmount ?? demoCase.expectedActionAmount ?? demoCase.proposedAmount,
    memory_enabled: memoryEnabled,
  };
}

async function postExperiment(path: string, payload: Record<string, unknown>): Promise<unknown> {
  return fetchJson<unknown>(
    path,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      timeoutMs: RUN_TIMEOUT_MS,
    },
    "Experiment request failed",
  );
}

async function consumeGraphStream(
  path: string,
  init: RequestInit,
  onEvent: (event: StreamEvent) => void,
): Promise<GraphRunResponse> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), RUN_TIMEOUT_MS);
  let result: AgentRunResponse | null = null;
  let threadId = "";
  let status: GraphRunResponse["status"] = "COMPLETED";
  let reviewSummary: ReviewSummary | null = null;
  let correctionId: string | null = null;

  try {
    const response = await fetch(path, { ...init, signal: controller.signal });
    if (!response.ok) throw new Error(`Graph stream failed: HTTP ${response.status}`);
    if (!response.headers.get("content-type")?.includes("text/event-stream")) {
      throw new Error("Graph stream returned an invalid content type");
    }
    if (!response.body) throw new Error("Graph stream did not include a response body");

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value, { stream: !done });
      const blocks = buffer.split("\n\n");
      buffer = blocks.pop() ?? "";
      for (const block of blocks) {
        const dataLine = block
          .split("\n")
          .find((line) => line.startsWith("data: "))
          ?.slice(6);
        if (!dataLine) continue;
        const event = JSON.parse(dataLine) as StreamEvent;
        onEvent(event);
        if (event.type === "graph.started") {
          threadId = String(event.data.thread_id ?? "");
        } else if (event.type === "run.result") {
          result = event.data as unknown as AgentRunResponse;
        } else if (event.type === "review.required") {
          status = "AWAITING_HUMAN";
          reviewSummary = event.data.review_summary as ReviewSummary;
          result = event.data.result as AgentRunResponse;
          threadId = String(event.data.thread_id ?? threadId);
        } else if (event.type === "graph.completed") {
          const completed = event.data as unknown as GraphRunResponse;
          status = completed.status;
          result = completed.result ?? result;
          reviewSummary = completed.review_summary ?? reviewSummary;
          correctionId = completed.correction_id ?? correctionId;
          threadId = completed.thread_id ?? threadId;
        }
      }
      if (done) break;
    }
  } finally {
    window.clearTimeout(timeout);
  }

  if (!result || !threadId) throw new Error("Graph stream ended without a persisted result");
  return {
    thread_id: threadId,
    status,
    result,
    review_summary: reviewSummary,
    correction_id: correctionId,
  };
}

type FetchJsonOptions = RequestInit & { timeoutMs: number };

async function fetchJson<T>(
  input: RequestInfo | URL,
  { timeoutMs, signal, ...init }: FetchJsonOptions,
  errorMessage: string,
): Promise<T> {
  const controller = new AbortController();
  const forwardAbort = () => controller.abort(signal?.reason);
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs);
  if (signal?.aborted) forwardAbort();
  signal?.addEventListener("abort", forwardAbort, { once: true });
  try {
    const response = await fetch(input, { ...init, signal: controller.signal });
    if (!response.ok) throw new Error(`${errorMessage}: HTTP ${response.status}`);
    if (!response.headers.get("content-type")?.includes("application/json")) {
      throw new Error(`${errorMessage}: expected JSON`);
    }
    return (await response.json()) as T;
  } finally {
    window.clearTimeout(timeout);
    signal?.removeEventListener("abort", forwardAbort);
  }
}
