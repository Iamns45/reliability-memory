"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { cases, DemoCase, traceSteps } from "./demo-data";
import {
  comparePolicyVersions,
  downloadEvidenceReceipt,
  expectsAwsRuntime,
  fetchAnalystCases,
  fetchAutonomyLedger,
  fetchEnvelope,
  fetchImpactSummary,
  fetchRuntimeHealth,
  injectRepeatedRequest,
  resumeHumanReview,
  runDemoCase,
  runMemoryAblation,
  simulateEvidenceFault,
  simulateDelayedOutcome,
  type AgentRunResponse,
  type AnalystCaseRecord,
  type AutonomyLedger,
  type EnvelopeRow,
  type ImpactSummary,
  type ReviewSummary,
  type RuntimeState,
  type StreamEvent,
  type WorkflowPlan,
} from "./runtime-client";

const money = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});

type RunState = "idle" | "running" | "complete";
type CaseSegment = "all" | "consumer" | "enterprise";

function BrandMark() {
  return (
    <span className="brand-mark" aria-hidden="true">
      <span>R</span>
      <i />
    </span>
  );
}

function StatusDot({ tone = "green" }: { tone?: "green" | "amber" | "red" }) {
  return <span className={`status-dot ${tone}`} aria-hidden="true" />;
}

function Icon({
  name,
}: {
  name: "memory" | "shield" | "spark" | "user" | "arrow" | "check" | "lock";
}) {
  const icons: Record<string, string> = {
    memory: "◎",
    shield: "◇",
    spark: "✦",
    user: "◉",
    arrow: "↗",
    check: "✓",
    lock: "⊘",
  };
  return (
    <span className={`text-icon icon-${name}`} aria-hidden="true">
      {icons[name]}
    </span>
  );
}

type DisplayDecision = AgentRunResponse["permission"]["mode"];

function DecisionBadge({ decision }: { decision: DisplayDecision }) {
  const label =
    decision === "AUTO"
      ? "Auto execute"
      : decision === "VERIFY"
        ? "Verify first"
        : decision === "DENY"
          ? "Denied"
          : "Human required";
  return <span className={`decision-badge decision-${decision.toLowerCase()}`}>{label}</span>;
}

function RiskBadge({ risk }: { risk: AgentRunResponse["permission"]["risk"] }) {
  return <span className={`risk-badge risk-${risk.toLowerCase()}`}>{risk} risk</span>;
}

function ReliabilityDial({ value, decision }: { value: number; decision: DisplayDecision }) {
  const hue =
    decision === "AUTO" ? "var(--green)" : decision === "VERIFY" ? "var(--amber)" : "var(--coral)";
  return (
    <div
      className="dial-shell"
      style={{ "--dial-value": `${value * 3.6}deg`, "--dial-color": hue } as React.CSSProperties}
    >
      <div className="dial-inner">
        <span className="dial-value">
          {value.toFixed(1)}
          <small>%</small>
        </span>
        <span className="dial-label">empirical reliability</span>
      </div>
    </div>
  );
}

function Header({ runtimeState }: { runtimeState: RuntimeState }) {
  const runtimeLabels: Record<RuntimeState, string> = {
    checking: "Connecting",
    live: "Decision service online",
    preview: "Case snapshot",
    error: "Decision service unavailable",
  };
  const statusTone =
    runtimeState === "error" ? "red" : runtimeState === "preview" ? "amber" : "green";

  return (
    <header className="topbar">
      <a className="brand" href="#top" aria-label="Reliability Memory home">
        <BrandMark />
        <span className="brand-copy">
          <strong>Reliability Memory</strong>
          <small>Resolution operations</small>
        </span>
      </a>
      <nav className="product-nav" aria-label="Product navigation">
        <a className="active" href="#case-workbench">
          Decision workspace
        </a>
        <a href="#autonomy-policy">Autonomy & audit</a>
      </nav>
      <div className="topbar-meta">
        <span className={`live-pill runtime-${runtimeState}`}>
          <StatusDot tone={statusTone} /> {runtimeLabels[runtimeState]}
        </span>
        <span className="analyst-profile">
          <span className="analyst-avatar">NA</span>
          <span>
            <strong>Nina Alvarez</strong>
            <small>Resolution analyst</small>
          </span>
        </span>
      </div>
    </header>
  );
}

function DecisionPath({
  runState,
  memoryEnabled,
  run,
  reviewSummary,
}: {
  runState: RunState;
  memoryEnabled: boolean;
  run: AgentRunResponse | null;
  reviewSummary: ReviewSummary | null;
}) {
  const evidenceStatus =
    runState === "running"
      ? "Checking records"
      : run?.resolution_evidence
        ? `${run.resolution_evidence.evidence_grade} grade · ${run.resolution_evidence.completed_sources.length}/${run.resolution_evidence.required_sources.length} admitted`
        : "Ready to verify";
  const memoryStatus = run
    ? run.evidence.memory_enabled
      ? `${run.similar_experiences.length} matching episodes`
      : "Ablation mode"
    : memoryEnabled
      ? "Enabled for this run"
      : "Disabled for comparison";
  const permissionStatus = run
    ? run.permission.mode === "AUTO"
      ? "Automatic execution"
      : run.permission.mode === "VERIFY"
        ? "Confirmation required"
        : run.permission.mode === "DENY"
          ? "Request denied"
          : "Specialist review"
    : "Calculated after evidence";
  const workflowStatus = run?.execution
    ? `${run.execution.steps.length} operations verified`
    : reviewSummary
      ? "Prefilled review ready"
      : run
        ? "Held by permission gate"
        : "No action taken yet";
  const stages = [
    {
      key: "case",
      label: "Case",
      title: "Request understood",
      detail: "Issue, customer, value, and desired outcome",
      status: "Selected",
    },
    {
      key: "evidence",
      label: "Current evidence",
      title: "Source facts verified",
      detail: "Freshness, identity, authority, and integrity",
      status: evidenceStatus,
    },
    {
      key: "memory",
      label: "Experience memory",
      title: "Past outcomes retrieved",
      detail: "Comparable episodes calibrate reliability only",
      status: memoryStatus,
    },
    {
      key: "permission",
      label: "Permission",
      title: "Policy sets the boundary",
      detail: "Evidence, risk, cost, novelty, and corrections",
      status: permissionStatus,
    },
    {
      key: "workflow",
      label: "Workflow",
      title: "Operations execute safely",
      detail: "Provider receipts, verification, and audit record",
      status: workflowStatus,
    },
  ];

  return (
    <section className="decision-path" aria-label="Evidence-to-action decision path">
      <div className="decision-path-heading">
        <div>
          <span>How to read this decision</span>
          <strong>Follow the same five colors through the detailed record</strong>
        </div>
        <small aria-live="polite">
          {runState === "running"
            ? "The backend is streaming each completed step"
            : run
              ? "Decision packet persisted"
              : "No customer operation occurs before the permission step"}
        </small>
      </div>
      <div className="decision-path-stages">
        {stages.map((stage, index) => (
          <article className={`decision-stage stage-${stage.key}`} key={stage.key}>
            <span className="decision-stage-number">{index + 1}</span>
            <div>
              <span>{stage.label}</span>
              <strong>{stage.title}</strong>
              <p>{stage.detail}</p>
              <small>{stage.status}</small>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

function ScenarioNav({
  items,
  selected,
  segment,
  onSegment,
  onSelect,
}: {
  items: DemoCase[];
  selected: string;
  segment: CaseSegment;
  onSegment: (segment: CaseSegment) => void;
  onSelect: (id: DemoCase["id"]) => void;
}) {
  return (
    <nav className="scenario-nav" aria-label="Analyst case queue">
      <div className="scenario-label">
        <span>Analyst queue</span>
        <strong>
          {items.length} visible · {cases.length} active
        </strong>
      </div>
      <div className="segment-filter" aria-label="Filter case segment">
        {(["all", "consumer", "enterprise"] as CaseSegment[]).map((item) => (
          <button
            type="button"
            className={segment === item ? "active" : ""}
            aria-pressed={segment === item}
            key={item}
            onClick={() => onSegment(item)}
          >
            {item === "all" ? "All operations" : item}
          </button>
        ))}
      </div>
      <div className="scenario-tabs" role="tablist">
        {items.map((demoCase, index) => (
          <button
            type="button"
            role="tab"
            aria-selected={selected === demoCase.id}
            className={selected === demoCase.id ? "active" : ""}
            key={demoCase.id}
            onClick={() => onSelect(demoCase.id)}
          >
            <span>{String(index + 1).padStart(2, "0")}</span>
            <div>
              <strong>{demoCase.customer}</strong>
              <small>{demoCase.tabLabel}</small>
            </div>
            <i className={`queue-dot queue-${demoCase.decision.toLowerCase()}`}>
              {demoCase.decision}
            </i>
          </button>
        ))}
      </div>
    </nav>
  );
}

function AnalystCaseFile({
  demoCase,
  record,
  run,
}: {
  demoCase: DemoCase;
  record: AnalystCaseRecord | null;
  run: AgentRunResponse | null;
}) {
  const customer = record?.customer ?? {
    customer_id: demoCase.customerId,
    display_name: demoCase.customer,
    account_type: demoCase.account.split(" · ")[0].toLowerCase(),
    region: demoCase.account.split(" · ")[1] ?? "US",
    contract_type: demoCase.contractType ?? "standard",
  };
  const sources =
    run?.resolution_evidence?.source_checks ?? record?.evidence_sources ?? demoCase.evidenceSources;
  const options =
    run?.resolution_evidence?.alternatives ??
    record?.resolution_options ??
    demoCase.resolutionOptions.map((option) => ({
      action: option.action,
      amount: option.action === "partial_refund" ? option.companyCost : option.customerValue,
      customer_value: option.customerValue,
      company_cost: option.companyCost,
      goal_fit: 1,
      eligible: true,
      permission_floor: demoCase.decision,
      auto_cost_cap: 150,
      safety_critical: false,
      selection_score: 0,
      selection_eligible: true,
      selection_exclusions: [],
      selected: false,
      value_components: [
        {
          label: "Resolved customer value",
          amount: option.customerValue,
          basis: "Case economics source",
        },
      ],
      label: option.label,
    }));
  const targetAction = run?.resolution_evidence?.recommended_action ?? "Selected during evaluation";
  const customerGoal =
    run?.resolution_evidence?.customer_goal ?? record?.customer_goal ?? demoCase.customerGoal;
  const businessGuardrail =
    run?.resolution_evidence?.business_guardrail ??
    record?.business_guardrail ??
    demoCase.businessGuardrail;
  const blockers = run?.resolution_evidence?.blocking_reasons ?? [];
  const evidenceGrade = run?.resolution_evidence?.evidence_grade;
  const evidenceAsOf = run?.resolution_evidence?.evidence_as_of ?? record?.evidence_as_of;
  return (
    <article className="analyst-case-file panel">
      <div className="case-file-header">
        <div>
          <span className="section-number">Case record</span>
          <h3>{record?.title ?? demoCase.title}</h3>
          <p>{record?.request_text ?? demoCase.request}</p>
        </div>
        <div className="case-file-source">
          <span>{record ? "Connected record" : "Case snapshot"}</span>
          <strong>{record ? "System of record" : demoCase.caseId}</strong>
        </div>
      </div>
      <div className="case-file-facts">
        {[
          ["Case", record?.case_id ?? demoCase.caseId],
          ["Customer", `${customer.display_name} · ${customer.customer_id}`],
          ["Account", `${customer.account_type} · ${customer.region}`],
          ["Contract", customer.contract_type],
          ["Task", record?.task_type ?? demoCase.taskType ?? demoCase.reason],
          ["Queue", record?.queue_status ?? demoCase.queueStatus ?? "OPEN"],
          ["Priority", record?.priority ?? demoCase.priority ?? "NORMAL"],
          ["Case value", money.format(record?.requested_amount ?? demoCase.amount)],
          ["Sources required", String(record?.evidence_required.length ?? sources.length)],
          [
            "Evidence snapshot",
            evidenceAsOf ? new Date(evidenceAsOf).toLocaleString() : "Created on run",
          ],
          ["Target action", targetAction.replaceAll("_", " ")],
        ].map(([label, value]) => (
          <div key={label}>
            <span>{label}</span>
            <strong>{value}</strong>
          </div>
        ))}
      </div>
      <div className="case-objectives">
        <div>
          <span>Customer outcome</span>
          <strong>{customerGoal}</strong>
        </div>
        <div>
          <span>Company guardrail</span>
          <strong>{businessGuardrail}</strong>
        </div>
      </div>
      <div className="evidence-source-grid">
        {sources.map((source) => {
          const provenance =
            "source_record_id" in source
              ? (source as {
                  source_record_id: string;
                  authority: string;
                  integrity: string;
                })
              : null;
          const checked = run
            ? (source as NonNullable<
                AgentRunResponse["resolution_evidence"]
              >["source_checks"][number])
            : null;
          const admitted = checked?.admissible ?? null;
          const freshness = checked?.freshness_status ?? "snapshot";
          const admissibilityReasons = checked?.admissibility_reasons ?? [];
          return (
            <section
              className={`evidence-source source-${admitted === false ? "blocked" : source.status}`}
              key={source.key}
            >
              <div>
                <span>{source.label}</span>
                <i>{admitted === null ? source.status : admitted ? "admissible" : "blocked"}</i>
              </div>
              <strong>{source.summary}</strong>
              {provenance && (
                <div className="evidence-provenance">
                  <code>{provenance.source_record_id}</code>
                  <span>{provenance.authority.replaceAll("_", " ")}</span>
                  <span>{freshness}</span>
                  <span>
                    {provenance.integrity === "sha256_verified" ? "hash verified" : "hash failed"}
                  </span>
                </div>
              )}
              <ul>
                {source.facts.map((fact) => (
                  <li key={fact}>{fact}</li>
                ))}
              </ul>
              {admissibilityReasons.map((reason) => (
                <p key={reason}>{reason}</p>
              ))}
            </section>
          );
        })}
      </div>
      <section className="resolution-matrix">
        <div className="case-file-kicker">
          <span>Resolution economics</span>
          <strong>{options.length} viable paths compared</strong>
        </div>
        <div className="resolution-option-grid">
          {options.map((option, index) => (
            <article
              className={option.selected ? "selected" : ""}
              key={`${option.action}-${index}`}
            >
              <span>{option.selected ? "Selected by resolver" : "Candidate"}</span>
              <strong>{option.label}</strong>
              <div>
                <small>Customer value</small>
                <b>{money.format(Number(option.customer_value))}</b>
              </div>
              <div>
                <small>Company cost</small>
                <b>{money.format(Number(option.company_cost))}</b>
              </div>
              <div>
                <small>Goal fit</small>
                <b>{Math.round(Number(option.goal_fit) * 100)}%</b>
              </div>
              {run && (
                <div>
                  <small>Selection score</small>
                  <b>{Number(option.selection_score ?? 0).toFixed(3)}</b>
                </div>
              )}
              {option.selected && option.value_components.length > 0 && (
                <ul className="value-breakdown">
                  {option.value_components.map((component) => (
                    <li key={component.label} title={component.basis}>
                      <span>{component.label}</span>
                      <strong>{money.format(Number(component.amount))}</strong>
                    </li>
                  ))}
                </ul>
              )}
            </article>
          ))}
        </div>
        <div className="selector-explanation">
          <span>How the option is selected</span>
          <strong>
            {run?.resolution_evidence?.selection_rationale ??
              "The resolver validates eligibility and case limits, then compares goal-adjusted customer value per company dollar. No preferred option is stored in the case."}
          </strong>
        </div>
      </section>
      <div className={`case-evidence-verdict ${blockers.length ? "blocked" : ""}`}>
        <Icon name={blockers.length ? "user" : "shield"} />
        <div>
          <span>Current evidence verdict</span>
          <strong>
            {blockers[0] ??
              (run?.resolution_evidence?.evidence_complete
                ? `${evidenceGrade} grade · ${run.resolution_evidence.completed_sources.length}/${run.resolution_evidence.required_sources.length} admissible records · ${run.resolution_evidence.recommended_action.replaceAll("_", " ")} recommended`
                : "Run the case to create a persisted decision packet from these source-specific facts")}
          </strong>
        </div>
      </div>
    </article>
  );
}

function ContainmentProofPanel({ run }: { run: AgentRunResponse | null }) {
  if (!run) {
    return (
      <article className="containment-proof panel containment-empty">
        <div className="panel-kicker">
          <span>Resolution record</span>
          <span className="source-tag">Created after execution</span>
        </div>
        <p>
          Run the case to create a permanent record of the admitted evidence, decision rule,
          workflow operations, verification result, and follow-up monitor.
        </p>
      </article>
    );
  }
  const proof = run.containment;
  return (
    <article className={`containment-proof panel proof-${proof.verified ? "verified" : "pending"}`}>
      <div className="panel-kicker">
        <span>Resolution record</span>
        <span className="source-tag">
          <StatusDot tone={proof.verified ? "green" : "amber"} />{" "}
          {proof.status.replaceAll("_", " ")}
        </span>
      </div>
      <div className="containment-headline">
        <div>
          <span>{proof.level.replaceAll("_", " ")}</span>
          <h3>{proof.root_cause}</h3>
        </div>
        <strong>{proof.evidence_grade}</strong>
      </div>
      <div className="containment-metrics">
        <div>
          <span>Admissible evidence</span>
          <strong>
            {proof.admissible_evidence_count}/{proof.required_evidence_count}
          </strong>
        </div>
        <div>
          <span>Executed operations</span>
          <strong>{proof.executed_operations}</strong>
        </div>
        <div>
          <span>Human time avoided</span>
          <strong>{proof.human_minutes_avoided} min</strong>
        </div>
        <div>
          <span>Company cost</span>
          <strong>{money.format(proof.estimated_company_cost)}</strong>
        </div>
        <div>
          <span>Customer value</span>
          <strong>{money.format(proof.customer_value)}</strong>
        </div>
      </div>
      <div className="containment-records">
        <span>Exact evidence receipt</span>
        {proof.evidence_record_ids.map((recordId) => (
          <code key={recordId}>{recordId}</code>
        ))}
      </div>
      <div className="containment-footer">
        <span>
          Rule <code>{proof.decision_rule}</code>
        </span>
        <span>
          Workflow <code>{proof.workflow_id ?? "awaiting permission"}</code>
        </span>
        <span>
          Monitor through <code>{new Date(proof.reopen_monitor_until).toLocaleString()}</code>
        </span>
      </div>
    </article>
  );
}

function McpVerificationPanel({ run }: { run: AgentRunResponse | null }) {
  const receipt = run?.mcp_verification;
  if (!receipt) return null;
  const active = receipt.endpoint !== "not-configured";
  const status = receipt.verified
    ? "Independent proof passed"
    : receipt.required
      ? "Execution contracted to review"
      : "Not enabled in this runtime";

  return (
    <article
      className={`mcp-verification panel ${receipt.verified ? "mcp-verified" : "mcp-unverified"}`}
    >
      <div className="panel-kicker">
        <span>Independent CockroachDB memory proof</span>
        <span className="source-tag">
          <StatusDot tone={receipt.verified ? "green" : "amber"} /> {status}
        </span>
      </div>
      <div className="mcp-proof-grid">
        <section>
          <span>Managed MCP connection</span>
          <strong>{active ? "Cluster scoped · read only" : "Local development mode"}</strong>
          <small>
            {active
              ? `${receipt.database} · ${receipt.cluster_scope.slice(0, 8)}…`
              : "AWS deployment requires this proof before autonomous execution."}
          </small>
        </section>
        <section>
          <span>Persisted episode</span>
          <strong>{receipt.observed_episode_id ? "Matched" : "Not independently observed"}</strong>
          <code>{receipt.observed_episode_id ?? receipt.episode_id}</code>
        </section>
        <section>
          <span>Distributed vector replay</span>
          <strong>
            {receipt.vector_check_performed
              ? `${receipt.matching_neighbor_ids.length}/${receipt.expected_neighbor_ids.length} neighbors matched`
              : "Not requested"}
          </strong>
          <small>Direct SQL retrieval cross-checked through {receipt.tool_name}</small>
        </section>
        <section>
          <span>Policy observation</span>
          <strong>{receipt.observed_decision ?? "Awaiting managed proof"}</strong>
          <small>{receipt.observed_policy_version ?? run.permission.policy_version}</small>
        </section>
      </div>
      <div className="mcp-receipt-line">
        <span>Verification receipt</span>
        <code>{receipt.receipt_hash}</code>
      </div>
      {receipt.failure_reason && active && <p className="mcp-failure">{receipt.failure_reason}</p>}
    </article>
  );
}

function CaseCard({
  demoCase,
  learned,
  run,
}: {
  demoCase: DemoCase;
  learned: boolean;
  run: AgentRunResponse | null;
}) {
  const current = run
    ? {
        customer:
          learned && demoCase.learned && run.case.customer_id === demoCase.learned.nextCustomerId
            ? demoCase.learned.nextCustomer
            : demoCase.customer,
        customerId: run.case.customer_id,
        request: run.case.request_text,
        amount: run.case.requested_amount,
        resolutionAmount: run.proposal.amount,
        action: run.proposal.action_type,
      }
    : learned && demoCase.learned
      ? {
          customer: demoCase.learned.nextCustomer,
          customerId: demoCase.learned.nextCustomerId,
          request: demoCase.learned.nextRequest,
          amount: demoCase.learned.nextAmount,
          resolutionAmount: demoCase.learned.nextProposedAmount,
          action: demoCase.actionType,
        }
      : {
          customer: demoCase.customer,
          customerId: demoCase.customerId,
          request: demoCase.request,
          amount: demoCase.amount,
          resolutionAmount: demoCase.proposedAmount,
          action: demoCase.actionType,
        };
  const metadataCaseId = run?.case.metadata.case_id;
  const displayedCaseId = typeof metadataCaseId === "string" ? metadataCaseId : demoCase.caseId;

  return (
    <article className="case-card panel">
      <div className="panel-kicker">
        <span>Incoming case</span>
        <span className="case-id">{displayedCaseId}</span>
      </div>
      <div className="customer-line">
        <div className="avatar">
          {current.customer
            .split(" ")
            .map((part) => part[0])
            .join("")
            .slice(0, 2)}
        </div>
        <div>
          <h3>{current.customer}</h3>
          <p>
            {current.customerId} · {demoCase.account}
          </p>
        </div>
        <RiskBadge risk={run?.permission.risk ?? demoCase.risk} />
      </div>
      <blockquote>“{current.request}”</blockquote>
      <div className="case-facts">
        <div>
          <span>Case value</span>
          <strong>{money.format(current.amount)}</strong>
        </div>
        <div>
          <span>Task class</span>
          <strong>{demoCase.reason}</strong>
        </div>
      </div>
      <div className="proposal-strip">
        <span>
          <Icon name="spark" /> Agent proposal
        </span>
        <strong>
          {current.action.replaceAll("_", " ")} · {money.format(current.resolutionAmount)}
        </strong>
        {run && <small className="api-origin-tag">system result</small>}
      </div>
    </article>
  );
}

function MemoryCard({
  demoCase,
  learned,
  run,
}: {
  demoCase: DemoCase;
  learned: boolean;
  run: AgentRunResponse | null;
}) {
  const liveSignals = run
    ? run.resolution_evidence
      ? run.resolution_evidence.source_checks.slice(0, 4).map((item) => ({
          label: item.label,
          value: item.status === "verified" ? "Verified" : "Review",
          detail: item.summary,
          tone: item.status === "verified" ? "positive" : "warning",
        }))
      : [
          {
            label: "Retrieved episodes",
            value: String(run.similar_experiences.length),
            detail: run.evidence.memory_enabled
              ? "Live vector + SQL retrieval"
              : "Memory ablation enabled",
            tone: run.evidence.memory_enabled ? "positive" : "warning",
          },
          {
            label: "Best similarity",
            value: `${Math.round((run.similar_experiences[0]?.similarity ?? 0) * 100)}%`,
            detail: "Semantic relevance, never permission",
            tone: "neutral",
          },
          {
            label: "Corrections found",
            value: String(run.evidence.relevant_corrections),
            detail: "Context-matched human lessons",
            tone: run.evidence.relevant_corrections ? "positive" : "neutral",
          },
          {
            label: "Evidence quality",
            value: run.evidence.evidence_quality,
            detail: `${run.evidence.verified_cases} independently verified cases`,
            tone: run.evidence.evidence_quality === "HIGH" ? "positive" : "warning",
          },
        ]
    : demoCase.memory;
  return (
    <article className="memory-card panel">
      <div className="panel-kicker">
        <span>Memory retrieved</span>
        <span className="source-tag">Experience store</span>
      </div>
      <div className="memory-grid">
        {liveSignals.map((signal, index) => {
          const isLearnedCorrection = !run && learned && demoCase.id === "learning" && index === 0;
          const isLearnedResolution = !run && learned && demoCase.id === "learning" && index === 1;
          return (
            <div className={`memory-signal ${signal.tone || "neutral"}`} key={signal.label}>
              <span>{signal.label}</span>
              <strong>
                {isLearnedCorrection ? "Found" : isLearnedResolution ? "Repair" : signal.value}
              </strong>
              <small>
                {isLearnedCorrection
                  ? "Verified 14-day warranty-grace lesson"
                  : isLearnedResolution
                    ? "Correction applied to matching service bulletin"
                    : signal.detail}
              </small>
            </div>
          );
        })}
      </div>
      <div
        className={`correction-callout ${learned || (run?.evidence.relevant_corrections ?? 0) > 0 ? "visible" : ""}`}
      >
        <Icon name="check" />
        <div>
          <strong>Verified correction retrieved</strong>
          <span>
            {run?.similar_experiences.find((item) => item.correction_lesson)?.correction_lesson ??
              demoCase.learned?.lesson}
          </span>
        </div>
      </div>
    </article>
  );
}

function GateCard({
  demoCase,
  runState,
  learned,
  run,
}: {
  demoCase: DemoCase;
  runState: RunState;
  learned: boolean;
  run: AgentRunResponse | null;
}) {
  const decision: DisplayDecision =
    run?.permission.mode ?? (learned && demoCase.id === "learning" ? "VERIFY" : demoCase.decision);
  const score = run
    ? run.evidence.reliability * 100
    : learned && demoCase.id === "learning"
      ? 82.4
      : demoCase.reliability;
  const reasons = run?.permission.reasons ?? demoCase.rationale;
  return (
    <article className={`gate-card panel ${runState === "complete" ? "resolved" : ""}`}>
      <div className="panel-kicker">
        <span>Evidence-qualified permission gate</span>
        <span className="locked-tag">
          <Icon name="lock" /> LLM cannot override
        </span>
      </div>
      <div className="gate-main">
        <ReliabilityDial value={score} decision={decision} />
        <div className="gate-decision">
          <span className="gate-label">Policy decision</span>
          <DecisionBadge decision={decision} />
          <p>
            {run
              ? `${run.permission.policy_version} · ${run.permission.rule_id}`
              : learned && demoCase.id === "learning"
                ? "The learned correction improves the proposal, but execution stays supervised until more replay evidence accrues."
                : demoCase.policy}
          </p>
        </div>
      </div>
      <div className="evidence-row">
        <div>
          <strong>
            {run?.evidence.verified_cases ??
              (learned && demoCase.id === "learning" ? 5 : demoCase.verifiedCases)}
          </strong>
          <span>verified cases</span>
        </div>
        <div>
          <strong>{run?.evidence.successes ?? demoCase.successes}</strong>
          <span>successful</span>
        </div>
        <div>
          <strong>{run?.evidence.human_overrides ?? demoCase.overrides}</strong>
          <span>human override</span>
        </div>
        <div>
          <strong>{run?.evidence.novelty ?? demoCase.novelty}</strong>
          <span>novelty</span>
        </div>
      </div>
      <div className="why-list">
        <span>Why this decision</span>
        <ul>
          {reasons.map((reason, index) => (
            <li key={reason}>
              <b>{index + 1}</b>
              {reason}
            </li>
          ))}
        </ul>
      </div>
    </article>
  );
}

function CounterfactualPanel({ run }: { run: AgentRunResponse | null }) {
  const explanation = run?.counterfactual;
  return (
    <article className="counterfactual-panel panel" aria-label="Decision counterfactual">
      <div className="panel-kicker">
        <span>What would make this automatic?</span>
        <span className="source-tag">Re-evaluated by policy</span>
      </div>
      {!run || !explanation ? (
        <p className="counterfactual-empty">
          Evaluate the case to calculate the exact evidence, outcome, and cost changes required to
          reach automatic execution.
        </p>
      ) : (
        <>
          <div
            className={`counterfactual-verdict ${explanation.attainable ? "attainable" : "guarded"}`}
          >
            <span>{explanation.attainable ? "Path validated" : "Hard boundary"}</span>
            <strong>{explanation.summary}</strong>
            <small>
              Current {run.permission.mode} → simulated {explanation.resulting_mode} · same policy
              version
            </small>
          </div>
          {explanation.requirements.length > 0 && (
            <div className="counterfactual-grid">
              {explanation.requirements.map((requirement) => (
                <section key={requirement.signal}>
                  <span>{requirement.signal.replaceAll("_", " ")}</span>
                  <strong>
                    {requirement.current} <i>→</i> {requirement.required}
                  </strong>
                  <p>{requirement.delta}</p>
                  <small>{requirement.rationale}</small>
                </section>
              ))}
            </div>
          )}
          {explanation.hard_boundaries.length > 0 && (
            <ul className="counterfactual-boundaries">
              {explanation.hard_boundaries.map((boundary) => (
                <li key={boundary}>{boundary}</li>
              ))}
            </ul>
          )}
        </>
      )}
    </article>
  );
}

function TracePanel({
  runState,
  activeStep,
  demoCase,
  learned,
  events,
}: {
  runState: RunState;
  activeStep: number;
  demoCase: DemoCase;
  learned: boolean;
  events: StreamEvent[];
}) {
  const backendEvents = events.filter(
    (event) => !["graph.started", "run.result", "graph.completed"].includes(event.type),
  );
  const labels: Record<string, string> = {
    "context.completed": "Customer context loaded",
    "case_evidence.completed": "Issue-specific evidence checked",
    "evidence.admissibility.completed": "Evidence provenance admitted",
    "memory.completed": "Experience memory retrieved",
    "proposal.completed": "Recommendation created",
    "policy.completed": "Deterministic policy evaluated",
    "workflow.planned": "Issue-specific workflow planned",
    "decision.persisted": "Episode persisted",
    "mcp.verification.started": "Managed MCP proof started",
    "mcp.verification.completed": "Managed MCP proof completed",
    "policy.contracted": "Permission contracted safely",
    "decision.reused": "Idempotent episode reused",
    "action.completed": "Provider action completed",
    "workflow.step.completed": "Workflow operation completed",
    "workflow.completed": "Workflow completed",
    "action.withheld": "Action withheld for review",
    "verification.completed": "Outcome independently verified",
    "review.required": "Review checkpoint created",
    "review.resumed": "Human review resumed",
    "graph.paused": "Checkpoint persisted",
  };
  const visibleBackendEvents = backendEvents.filter((event) => labels[event.type]).slice(-8);
  return (
    <article className="trace-panel panel">
      <div className="panel-kicker">
        <span>Agent execution trace</span>
        <span className="trace-status">
          <StatusDot tone={runState === "running" ? "amber" : "green"} />{" "}
          {runState === "running" ? "Running" : runState === "complete" ? "Verified" : "Ready"}
        </span>
      </div>
      <div className="trace-list">
        {visibleBackendEvents.length > 0
          ? visibleBackendEvents.map((event, index) => (
              <div className="trace-step done" key={`${event.type}-${index}`}>
                <span className="trace-node">✓</span>
                <div className="trace-copy">
                  <strong>{labels[event.type]}</strong>
                  <small>{JSON.stringify(event.data).slice(0, 112)}</small>
                </div>
                <code>backend SSE</code>
                <span className="latency">live</span>
              </div>
            ))
          : traceSteps.map((step, index) => {
              const isDone = runState === "complete" || index < activeStep;
              const isActive = runState === "running" && index === activeStep;
              const detail =
                learned && demoCase.id === "learning" && index === 1
                  ? "Found correction EP-8410 · 96% semantic match"
                  : step.detail;
              return (
                <div
                  className={`trace-step ${isDone ? "done" : ""} ${isActive ? "active" : ""}`}
                  key={step.name}
                >
                  <span className="trace-node">{isDone ? "✓" : index + 1}</span>
                  <div className="trace-copy">
                    <strong>{step.name}</strong>
                    <small>{detail}</small>
                  </div>
                  <code>{step.tool}</code>
                  <span className="latency">{isDone || isActive ? step.latency : "—"}</span>
                </div>
              );
            })}
      </div>
    </article>
  );
}

function EvidencePanel({ demoCase, run }: { demoCase: DemoCase; run: AgentRunResponse | null }) {
  const similar = run
    ? run.similar_experiences.map((item) => ({
        id: item.episode_id,
        summary: item.summary,
        similarity: Math.round(item.similarity * 100),
        outcome: item.correction_lesson
          ? ("corrected" as const)
          : item.verified_success
            ? ("verified" as const)
            : ("failed" as const),
      }))
    : demoCase.similar;
  return (
    <article className="evidence-panel panel">
      <div className="panel-kicker">
        <span>Nearest verified experience</span>
        <span className="source-tag">Vector + SQL</span>
      </div>
      <div className="similar-list">
        {similar.map((item) => (
          <div className="similar-item" key={item.id}>
            <div className="similar-top">
              <code title={item.id}>{item.id.length > 16 ? item.id.slice(0, 8) : item.id}</code>
              <span className={`outcome outcome-${item.outcome}`}>{item.outcome}</span>
              <strong>{item.similarity}%</strong>
            </div>
            <p>{item.summary}</p>
            <div className="similarity-bar">
              <i style={{ width: `${item.similarity}%` }} />
            </div>
          </div>
        ))}
      </div>
      <p className="evidence-note">
        <Icon name="shield" /> Past cases calibrate reliability. Current source systems prove this
        issue and bound the remedy.
      </p>
    </article>
  );
}

function WorkflowPanel({
  run,
  reviewSummary,
  demoCase,
}: {
  run: AgentRunResponse | null;
  reviewSummary: ReviewSummary | null;
  demoCase: DemoCase;
}) {
  const plan = run?.workflow_plan ?? reviewSummary?.workflow_plan ?? previewWorkflowPlan(demoCase);

  const execution = run?.execution;
  const isPreview = !run && !reviewSummary;
  const stepResults = new Map(execution?.steps.map((step) => [step.step_id, step]) ?? []);
  const artifacts = Object.entries(execution?.artifacts ?? {});
  return (
    <article className="workflow-panel panel" aria-label="Agent workflow execution">
      <div className="panel-kicker">
        <span>Decision → execution workflow</span>
        <span className={`workflow-state ${execution ? "executed" : "planned"}`}>
          <StatusDot tone={execution ? "green" : "amber"} />
          {execution ? "Executed" : isPreview ? "Expected workflow" : "Awaiting permission"}
        </span>
      </div>
      <div className="workflow-summary">
        <div>
          <span>{plan.workflow_type.replaceAll("_", " ")}</span>
          <h3>{plan.name}</h3>
          <p>{plan.objective}</p>
        </div>
        <div className="workflow-receipt">
          <span>Workflow receipt</span>
          <code>
            {execution?.workflow_id ??
              (isPreview ? "Created after execution" : "Created after permission")}
          </code>
        </div>
      </div>
      <div className="workflow-steps">
        {plan.steps.map((step, index) => {
          const result = stepResults.get(step.step_id);
          return (
            <div className={`workflow-step ${result ? "complete" : "pending"}`} key={step.step_id}>
              <span className="workflow-step-number">{result ? "✓" : index + 1}</span>
              <div className="workflow-step-copy">
                <span>{step.system}</span>
                <strong>{step.title}</strong>
                <small>{step.detail}</small>
              </div>
              <div className="workflow-step-proof">
                <span>{result?.status ?? "planned"}</span>
                <code>{result?.provider_reference ?? step.operation}</code>
              </div>
            </div>
          );
        })}
      </div>
      <div className="workflow-footer">
        <p>
          <Icon name="shield" /> <strong>Compensation:</strong> {plan.compensation}
        </p>
        {artifacts.length > 0 && (
          <div className="workflow-artifacts">
            {artifacts.map(([name, reference]) => (
              <span key={name}>
                {name.replaceAll("_", " ")} <code>{reference}</code>
              </span>
            ))}
          </div>
        )}
      </div>
    </article>
  );
}

function previewWorkflowPlan(demoCase: DemoCase): WorkflowPlan {
  const templates: Record<
    string,
    { name: string; steps: Array<[string, string, string]>; compensation: string }
  > = {
    replacement: {
      name: "Replacement recovery",
      steps: [
        ["Inventory", "Reserve replacement inventory", "reserve_replacement"],
        ["Fulfillment", "Create replacement order", "create_replacement_order"],
        ["Quality", "Open product quality signal", "open_quality_signal"],
        ["Customer communications", "Send tracking and guidance", "send_replacement_notice"],
      ],
      compensation: "Cancel unshipped fulfillment and release reserved inventory.",
    },
    reship: {
      name: "Fulfillment recovery",
      steps: [
        ["Order management", "Validate fulfillment exception", "validate_exception"],
        ["Inventory", "Reserve missing inventory", "reserve_reship_inventory"],
        ["Fulfillment", "Create priority shipment", "create_priority_reship"],
        ["Customer communications", "Send recovery update", "send_reship_notice"],
      ],
      compensation: "Cancel the unshipped reship and release the inventory reservation.",
    },
    exchange: {
      name: "Verified product exchange",
      steps: [
        ["Inventory", "Reserve correct variant", "reserve_exchange_variant"],
        ["Returns", "Create prepaid return", "create_exchange_return"],
        ["Fulfillment", "Create exchange shipment", "create_exchange_shipment"],
        ["Customer communications", "Send exchange instructions", "send_exchange_notice"],
      ],
      compensation: "Cancel unshipped legs and release the correct variant reservation.",
    },
    ship_missing_part: {
      name: "Missing component recovery",
      steps: [
        ["Parts inventory", "Reserve exact component", "reserve_missing_component"],
        ["Fulfillment", "Create component shipment", "create_component_shipment"],
        ["Order management", "Update order completeness", "update_order_completeness"],
        ["Customer communications", "Send installation guidance", "send_component_guidance"],
      ],
      compensation: "Cancel the unshipped component and release the parts reservation.",
    },
    partial_refund: {
      name: "Retain-and-adjust resolution",
      steps: [
        ["Payments", "Create bounded adjustment", "create_partial_adjustment"],
        ["Payments", "Issue partial refund", "issue_partial_refund"],
        ["Order management", "Record retained-product agreement", "record_keep_agreement"],
        ["Customer communications", "Send adjustment receipt", "send_adjustment_notice"],
      ],
      compensation: "Reconcile the payment and ledger receipts without duplicating the adjustment.",
    },
    refund: {
      name: "Payment reversal",
      steps: [
        ["Payments", "Lock verified transaction", "lock_payment_transaction"],
        ["Payments", "Issue payment refund", "issue_refund"],
        ["Finance ledger", "Write credit memo", "write_credit_memo"],
        ["Customer communications", "Send refund receipt", "send_refund_notice"],
      ],
      compensation: "Reconcile the same provider receipt before any retry is attempted.",
    },
    store_credit: {
      name: "Bounded account credit",
      steps: [
        ["Customer ledger", "Validate credit eligibility", "validate_credit_eligibility"],
        ["Customer ledger", "Issue account credit", "issue_store_credit"],
        ["Policy service", "Attach expiry and scope", "attach_credit_terms"],
        ["Customer communications", "Send credit receipt", "send_credit_notice"],
      ],
      compensation: "Void unused credit and retain the audit trail if a later step fails.",
    },
    warranty_repair: {
      name: "Warranty service recovery",
      steps: [
        ["Warranty", "Create repair authorization", "create_repair_authorization"],
        ["Service network", "Reserve repair capacity", "reserve_repair_capacity"],
        ["Returns", "Create prepaid logistics", "create_repair_logistics"],
        ["Customer communications", "Send service timeline", "send_repair_timeline"],
      ],
      compensation: "Cancel unused logistics and release the service reservation.",
    },
    guided_troubleshooting: {
      name: "Guided product recovery",
      steps: [
        ["Knowledge service", "Select verified diagnostic", "select_diagnostic_playbook"],
        ["Support automation", "Start guided session", "start_guided_session"],
        ["Device diagnostics", "Capture diagnostic result", "capture_diagnostic_result"],
        ["Case management", "Set follow-up trigger", "set_followup_trigger"],
      ],
      compensation: "Preserve captured diagnostics and escalate if the symptom persists.",
    },
    safety_escalation: {
      name: "Product safety response",
      steps: [
        ["Product safety", "Create safety incident", "create_safety_incident"],
        ["Customer communications", "Send stop-use notice", "send_stop_use_notice"],
        ["Hazmat logistics", "Arrange safe recovery", "arrange_safe_recovery"],
        ["Quality", "Place product safety signal", "place_product_safety_signal"],
        ["Incident management", "Page safety owner", "page_safety_owner"],
      ],
      compensation: "Keep safety notifications active and escalate failed recovery steps.",
    },
    seller_investigation: {
      name: "Marketplace integrity response",
      steps: [
        ["Trust and safety", "Preserve claim evidence", "preserve_claim_evidence"],
        ["Marketplace ledger", "Hold seller settlement", "hold_seller_settlement"],
        ["Trust and safety", "Open seller investigation", "open_seller_investigation"],
        ["Order management", "Create customer remedy", "create_marketplace_remedy"],
        ["Incident management", "Notify integrity analyst", "notify_integrity_analyst"],
      ],
      compensation: "Keep preserved evidence and route failed financial holds to an analyst.",
    },
    cost_containment: {
      name: "Verified cost containment",
      steps: [
        ["Infrastructure inventory", "Create recovery snapshot", "create_recovery_snapshot"],
        ["Resource controller", "Schedule bounded shutdown", "schedule_idle_resource_shutdown"],
        ["Cost control", "Install anomaly guardrail", "create_cost_anomaly_guardrail"],
        [
          "Customer communications",
          "Send savings and recovery plan",
          "send_cost_containment_notice",
        ],
      ],
      compensation: "Restart the preserved resource if a verified dependency appears.",
    },
    rollback_deployment: {
      name: "Safe release rollback",
      steps: [
        ["Deployment controller", "Freeze failed release", "freeze_failed_release"],
        ["Deployment controller", "Restore last healthy artifact", "restore_healthy_release"],
        ["Observability", "Run recovery health gates", "verify_service_recovery"],
        ["Change management", "Open root-cause record", "open_deployment_rca"],
        ["Customer communications", "Notify service owners", "send_recovery_notice"],
      ],
      compensation: "Reapply only after root cause correction and passing every health gate.",
    },
    least_privilege_fix: {
      name: "Least-privilege access recovery",
      steps: [
        ["Authorization service", "Revalidate policy simulation", "revalidate_policy_simulation"],
        ["Identity management", "Stage scoped policy change", "stage_least_privilege_policy"],
        ["Identity management", "Apply owner-approved grant", "apply_least_privilege_grant"],
        ["Authorization service", "Verify allowed and denied paths", "verify_policy_boundaries"],
        ["Customer communications", "Send access receipt", "send_access_recovery_notice"],
      ],
      compensation: "Remove the grant and restore the prior policy if verification fails.",
    },
    database_capacity_recovery: {
      name: "Reversible database capacity recovery",
      steps: [
        [
          "Database control plane",
          "Provision temporary read capacity",
          "provision_temporary_read_capacity",
        ],
        ["Database routing", "Rebalance read traffic", "rebalance_read_traffic"],
        ["Observability", "Verify latency recovery", "verify_database_recovery"],
        ["Capacity control", "Attach automatic expiry", "schedule_capacity_expiry"],
      ],
      compensation: "Safely rebalance traffic and remove temporary capacity.",
    },
    traffic_stabilization: {
      name: "API traffic stabilization",
      steps: [
        ["Traffic control", "Apply bounded retry policy", "apply_retry_backoff_policy"],
        ["Request queue", "Activate queue protection", "activate_queue_protection"],
        ["Observability", "Verify completion rate", "verify_traffic_recovery"],
        ["Traffic control", "Set automatic rollback threshold", "set_traffic_rollback_threshold"],
      ],
      compensation: "Restore the prior retry policy if completion or error thresholds regress.",
    },
    security_containment: {
      name: "Privileged credential containment",
      steps: [
        ["Security audit", "Seal forensic evidence", "seal_forensic_evidence"],
        ["Identity management", "Revoke suspicious session", "revoke_suspicious_session"],
        ["Secrets management", "Rotate affected credential", "rotate_compromised_credential"],
        ["Security control", "Isolate affected workload", "isolate_affected_workload"],
        ["Incident management", "Open security incident", "open_security_incident"],
      ],
      compensation: "The incident commander owns any restoration of revoked access.",
    },
    isolated_restore: {
      name: "Isolated data recovery",
      steps: [
        ["Recovery service", "Create isolated recovery target", "create_isolated_restore_target"],
        ["Backup service", "Restore immutable recovery point", "restore_verified_backup"],
        ["Data verification", "Run integrity verification", "verify_restored_data"],
        ["Change management", "Create promotion request", "create_restore_promotion_request"],
        ["Customer communications", "Send recovery evidence", "send_restore_evidence"],
      ],
      compensation: "Delete only the isolated target; never modify current production data.",
    },
    quota_adjustment: {
      name: "Bounded temporary quota adjustment",
      steps: [
        ["Capacity service", "Revalidate calculated need", "revalidate_quota_need"],
        ["Quota service", "Request bounded temporary quota", "request_temporary_quota"],
        ["Cost control", "Attach budget controls", "attach_quota_budget_controls"],
        ["Quota service", "Schedule quota expiry", "schedule_quota_expiry"],
        ["Customer communications", "Send capacity receipt", "send_quota_notice"],
      ],
      compensation: "Return to the prior quota if budget or abuse controls trigger.",
    },
    deny: {
      name: "Evidence-based denial and appeal",
      steps: [
        ["Case management", "Record evidence-based denial", "record_denial"],
        ["Case management", "Create appeal path", "create_appeal_path"],
        ["Customer communications", "Send decision explanation", "send_denial_explanation"],
      ],
      compensation: "Reopen the case when the missing evidence arrives through the appeal path.",
    },
  };
  const selected = templates[demoCase.actionType] ?? templates.deny;
  return {
    workflow_type: `${demoCase.taskType}:${demoCase.actionType}`,
    name: selected.name,
    objective: demoCase.customerGoal,
    steps: selected.steps.map(([system, title, operation], index) => ({
      step_id: `${String(index + 1).padStart(2, "0")}-${operation.replaceAll("_", "-")}`,
      title,
      system,
      operation,
      detail: `${title} after the evidence-qualified permission is granted.`,
      reversible: index < 2,
    })),
    compensation: selected.compensation,
  };
}

function CorrectionPanel({
  demoCase,
  learned,
  correctionId,
  reviewSummary,
  canTeach,
  teaching,
  error,
  onTeach,
}: {
  demoCase: DemoCase;
  learned: boolean;
  correctionId: string | null;
  reviewSummary: ReviewSummary | null;
  canTeach: boolean;
  teaching: boolean;
  error: string | null;
  onTeach: () => void;
}) {
  if (!demoCase.learned && !reviewSummary) return null;

  const buttonLabel = correctionId
    ? "Correction stored in memory"
    : learned && reviewSummary
      ? "Approve supervised replay"
      : learned
        ? "Correction ready for replay"
        : teaching
          ? "Storing verified correction"
          : canTeach
            ? "Verify & teach the agent"
            : "Run the case before teaching";

  return (
    <article className={`correction-panel ${learned ? "learned" : ""}`}>
      <div className="correction-before">
        <span>Human review summary</span>
        <strong>{reviewSummary?.headline ?? "Agent proposed a generic goodwill credit"}</strong>
        <small>
          {reviewSummary?.reviewer_task ?? "Confirm the suggested correction; edit only if needed."}
        </small>
      </div>
      <div className="correction-arrow">→</div>
      <div className="correction-human">
        <span>Human correction</span>
        <strong>
          {reviewSummary
            ? `${reviewSummary.suggested_resolution.action_type.replace("_", " ")} · ${money.format(reviewSummary.suggested_resolution.amount)}`
            : demoCase.learned?.correction}
        </strong>
        <small>
          Reason: {reviewSummary?.suggested_resolution.reason ?? demoCase.learned?.lesson}
        </small>
        {correctionId && <code>Correction ID · {correctionId}</code>}
      </div>
      <button
        className="teach-button"
        type="button"
        onClick={onTeach}
        disabled={Boolean(correctionId) || teaching || !canTeach}
      >
        <Icon name={learned ? "check" : "memory"} /> {buttonLabel}
      </button>
      {error && (
        <p className="correction-error" role="alert">
          {error}
        </p>
      )}
    </article>
  );
}

function QueueSummary() {
  const autoCount = cases.filter((item) => item.decision === "AUTO").length;
  const verifyCount = cases.filter((item) => item.decision === "VERIFY").length;
  const humanCount = cases.filter((item) => item.decision === "HUMAN").length;
  const enterpriseCount = cases.filter((item) => item.customerSegment === "enterprise").length;
  return (
    <section className="metric-strip" aria-label="Case queue summary">
      <div>
        <span className="metric-number">{cases.length}</span>
        <span>Open cases</span>
        <small>Current case catalog</small>
      </div>
      <div>
        <span className="metric-number">{autoCount}</span>
        <span>Auto eligible</span>
        <small>Subject to current evidence</small>
      </div>
      <div>
        <span className="metric-number">{verifyCount}</span>
        <span>Needs confirmation</span>
        <small>Customer or analyst check</small>
      </div>
      <div>
        <span className="metric-number">{humanCount}</span>
        <span>Specialist review</span>
        <small>High-risk or novel context</small>
      </div>
      <div>
        <span className="metric-number">{enterpriseCount}</span>
        <span>Enterprise cases</span>
        <small>{cases.length - enterpriseCount} consumer cases</small>
      </div>
    </section>
  );
}

function EnvelopeSection({
  liveRows,
  impact,
  ledger,
}: {
  liveRows: EnvelopeRow[];
  impact: ImpactSummary | null;
  ledger: AutonomyLedger | null;
}) {
  const fallbackRows = [
    {
      skill: "Early failure · diagnostics + warranty + safe batch",
      samples: "500",
      reliable: "99.2%",
      mode: "AUTO",
      trend: "+0.3",
    },
    {
      skill: "Damaged but functional · customer keep offer",
      samples: "164",
      reliable: "96.8%",
      mode: "VERIFY",
      trend: "+0.2",
    },
    {
      skill: "Product safety · thermal or electrical signal",
      samples: "28",
      reliable: "96.1%",
      mode: "HUMAN",
      trend: "guarded",
    },
    {
      skill: "Serialized return · identity mismatch",
      samples: "112",
      reliable: "98.4%",
      mode: "DENY",
      trend: "stable",
    },
    {
      skill: "Warranty grace · verified correction replay",
      samples: "42",
      reliable: "93.4%",
      mode: "HUMAN",
      trend: "+4.7",
    },
  ];
  const rows = liveRows.length
    ? liveRows.map((row) => ({
        skill: row.context,
        samples: String(row.evidence.verified_cases),
        reliable: `${(row.evidence.reliability * 100).toFixed(1)}%`,
        mode: row.permission.mode,
        trend: "live",
      }))
    : fallbackRows;
  return (
    <section className="envelope-section" id="autonomy-policy">
      <div className="section-heading">
        <div>
          <span className="section-number">Policy administration</span>
          <h2>Autonomy by operating context</h2>
        </div>
        <p>
          Permission is calculated independently for each task and context. Similar cases can inform
          the reliability estimate, but only current admitted evidence can authorize work.
        </p>
      </div>
      <div className="envelope-table">
        <div className="envelope-head">
          <span>Reliability envelope</span>
          <span>Evidence</span>
          <span>Reliability</span>
          <span>Autonomy</span>
          <span>30d</span>
        </div>
        {rows.map((row) => (
          <div className="envelope-row" key={row.skill}>
            <span>
              <StatusDot
                tone={row.mode === "AUTO" ? "green" : row.mode === "VERIFY" ? "amber" : "red"}
              />
              {row.skill}
            </span>
            <strong>{row.samples}</strong>
            <strong>{row.reliable}</strong>
            <DecisionBadge decision={row.mode as DisplayDecision} />
            <span className="trend">↗ {row.trend}</span>
          </div>
        ))}
      </div>
      {impact && (
        <section className="impact-summary" aria-label="Observed economic impact">
          <div>
            <span>Verified outcome cohort</span>
            <strong>{impact.verified_outcomes.toLocaleString()}</strong>
            <small>{impact.task_contexts} evidence-specific contexts</small>
          </div>
          <div>
            <span>Customer value delivered</span>
            <strong>{money.format(impact.customer_value_delivered)}</strong>
            <small>{impact.successful_outcomes.toLocaleString()} successful outcomes</small>
          </div>
          <div>
            <span>Evidence-selected cost</span>
            <strong>{money.format(impact.evidence_selected_company_cost)}</strong>
            <small>{money.format(impact.refund_first_baseline_cost)} refund-first baseline</small>
          </div>
          <div>
            <span>Estimated cost avoided</span>
            <strong>{money.format(impact.estimated_cost_avoided)}</strong>
            <small title={impact.methodology}>Measured with the visible case economics</small>
          </div>
        </section>
      )}
      {ledger && (
        <section className="autonomy-ledger" aria-label="Autonomy audit ledger">
          <div className="case-file-kicker">
            <span>Hash-chained autonomy register</span>
            <strong>{ledger.entry_count} dated policy records</strong>
          </div>
          <div className="ledger-list">
            {ledger.entries.slice(0, 5).map((entry) => (
              <article key={entry.entry_hash}>
                <span>{entry.event === "AUTONOMY_EARNED" ? "Earned" : "Withheld"}</span>
                <strong>{entry.context}</strong>
                <small>
                  {entry.verified_cases} verified · {(entry.reliability * 100).toFixed(1)}% ·{" "}
                  {entry.mode}
                </small>
                <code title={entry.entry_hash}>{entry.entry_hash.slice(0, 12)}</code>
              </article>
            ))}
          </div>
          <p>
            Ledger head <code>{ledger.head_hash.slice(0, 20)}</code>. Every entry includes the
            previous hash, so a changed authority record is detectable.
          </p>
        </section>
      )}
    </section>
  );
}

function ReliabilityLab({
  live,
  run,
  busy,
  result,
  onAblation,
  onIdempotency,
  onChargeback,
  onPolicyCompare,
  onReceipt,
  onCorruptHash,
  onStaleRecord,
  onMismatchCorrelation,
}: {
  live: boolean;
  run: AgentRunResponse | null;
  busy: string | null;
  result: string;
  onAblation: () => void;
  onIdempotency: () => void;
  onChargeback: () => void;
  onPolicyCompare: () => void;
  onReceipt: () => void;
  onCorruptHash: () => void;
  onStaleRecord: () => void;
  onMismatchCorrelation: () => void;
}) {
  const controls = [
    ["Memory ablation", "Compare the same case with and without retrieved evidence.", onAblation],
    [
      "Retry safety",
      "Send one idempotency key twice and prove one provider action.",
      onIdempotency,
    ],
    [
      "Policy v4.9 ↔ v5.0",
      "Show why the old amount threshold auto-executes while v5.0 requires the right confirmation.",
      onPolicyCompare,
    ],
    [
      "Delayed outcome",
      "Turn a later adverse customer or provider outcome into lower reliability.",
      onChargeback,
    ],
    [
      "Evidence receipt",
      "Download the persisted episode, outcome, review, and correction IDs.",
      onReceipt,
    ],
    [
      "Corrupt evidence hash",
      "Change one digest byte and watch the evidence grade block execution.",
      onCorruptHash,
    ],
    [
      "Expire source record",
      "Age one record past its freshness window and re-run admission only.",
      onStaleRecord,
    ],
    [
      "Break entity match",
      "Attach one record to another customer and prove correlation blocks it.",
      onMismatchCorrelation,
    ],
  ] as const;
  return (
    <section className="reliability-lab panel" aria-label="Verification controls">
      <div className="panel-kicker">
        <span>Verification tools</span>
        <span className="source-tag">Controlled checks</span>
      </div>
      <div className="lab-grid">
        {controls.map(([title, detail, action]) => {
          const needsRun = title === "Delayed outcome" || title === "Evidence receipt";
          const needsExecution = title === "Delayed outcome";
          const disabled =
            !live || Boolean(busy) || (needsRun && !run) || (needsExecution && !run?.execution);
          return (
            <button type="button" key={title} onClick={action} disabled={disabled}>
              <strong>{busy === title ? "Running…" : title}</strong>
              <small>{detail}</small>
            </button>
          );
        })}
      </div>
      <pre className={result ? "visible" : ""} aria-live="polite">
        {result || "Select a check to inspect the supporting system record."}
      </pre>
    </section>
  );
}

function Footer() {
  return (
    <footer>
      <div className="footer-brand">
        <BrandMark />
        <div>
          <strong>Reliability Memory</strong>
          <span>Resolution operations</span>
        </div>
      </div>
      <div className="footer-tech">
        <span>Evidence policy v5.0</span>
        <i>·</i>
        <span>Audit logging enabled</span>
      </div>
      <p>
        Provider operations use deterministic sandbox receipts in this preview; policy, persistence,
        replay, and verification run normally.
      </p>
    </footer>
  );
}

export default function ReliabilityDashboard() {
  const [selectedId, setSelectedId] = useState("damaged");
  const [caseSegment, setCaseSegment] = useState<CaseSegment>("consumer");
  const [runState, setRunState] = useState<RunState>("idle");
  const [activeStep, setActiveStep] = useState(0);
  const [learned, setLearned] = useState(false);
  const [memoryEnabled, setMemoryEnabled] = useState(true);
  const [runtimeState, setRuntimeState] = useState<RuntimeState>("checking");
  const [liveRun, setLiveRun] = useState<AgentRunResponse | null>(null);
  const [threadId, setThreadId] = useState<string | null>(null);
  const [reviewSummary, setReviewSummary] = useState<ReviewSummary | null>(null);
  const [streamEvents, setStreamEvents] = useState<StreamEvent[]>([]);
  const [teaching, setTeaching] = useState(false);
  const [correctionId, setCorrectionId] = useState<string | null>(null);
  const [correctionError, setCorrectionError] = useState<string | null>(null);
  const [envelopeRows, setEnvelopeRows] = useState<EnvelopeRow[]>([]);
  const [impactSummary, setImpactSummary] = useState<ImpactSummary | null>(null);
  const [autonomyLedger, setAutonomyLedger] = useState<AutonomyLedger | null>(null);
  const [catalogCases, setCatalogCases] = useState<AnalystCaseRecord[]>([]);
  const [labBusy, setLabBusy] = useState<string | null>(null);
  const [labResult, setLabResult] = useState("");
  const runToken = useRef(0);
  const visibleCases = useMemo(
    () =>
      caseSegment === "all" ? cases : cases.filter((item) => item.customerSegment === caseSegment),
    [caseSegment],
  );
  const demoCase = useMemo(
    () => cases.find((item) => item.id === selectedId) || cases[0],
    [selectedId],
  );
  const catalogCase = useMemo(
    () => catalogCases.find((item) => item.case_id === demoCase.caseId) ?? null,
    [catalogCases, demoCase.caseId],
  );

  useEffect(
    () => () => {
      runToken.current += 1;
    },
    [],
  );

  useEffect(() => {
    const controller = new AbortController();
    fetchRuntimeHealth(controller.signal)
      .then((health) => {
        const productionServicesReady =
          health.memory === "cockroachdb" &&
          health.model === "amazon-bedrock" &&
          health.mcp.status === "configured" &&
          health.mcp.required_for_autonomy;
        setRuntimeState(expectsAwsRuntime() && !productionServicesReady ? "error" : "live");
        if (productionServicesReady || !expectsAwsRuntime()) {
          fetchEnvelope()
            .then(setEnvelopeRows)
            .catch(() => setEnvelopeRows([]));
          fetchAnalystCases()
            .then(setCatalogCases)
            .catch(() => setCatalogCases([]));
          fetchImpactSummary()
            .then(setImpactSummary)
            .catch(() => setImpactSummary(null));
          fetchAutonomyLedger()
            .then(setAutonomyLedger)
            .catch(() => setAutonomyLedger(null));
        }
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          setRuntimeState(expectsAwsRuntime() ? "error" : "preview");
        }
      });
    return () => controller.abort();
  }, []);

  const chooseCase = (id: string) => {
    runToken.current += 1;
    setSelectedId(id);
    setRunState("idle");
    setActiveStep(0);
    setLearned(false);
    setMemoryEnabled(true);
    setLiveRun(null);
    setThreadId(null);
    setReviewSummary(null);
    setStreamEvents([]);
    setTeaching(false);
    setCorrectionId(null);
    setCorrectionError(null);
    setLabResult("");
  };

  const chooseSegment = (segment: CaseSegment) => {
    setCaseSegment(segment);
    const first = cases.find((item) => segment === "all" || item.customerSegment === segment);
    if (first) chooseCase(first.id);
  };

  const runCase = async () => {
    const token = ++runToken.current;
    setRunState("running");
    setLiveRun(null);
    setReviewSummary(null);
    setStreamEvents([]);
    setCorrectionError(null);
    const shouldCallAws = runtimeState === "live" || expectsAwsRuntime();
    try {
      if (shouldCallAws) {
        const response = await runDemoCase(demoCase, learned, memoryEnabled, (event) => {
          if (token === runToken.current) setStreamEvents((current) => [...current, event]);
        });
        if (token !== runToken.current) return;
        setLiveRun(response.result);
        setThreadId(response.thread_id);
        setReviewSummary(response.review_summary ?? null);
        setCorrectionId(response.correction_id ?? null);
        setRuntimeState("live");
      } else {
        for (let index = 0; index < traceSteps.length; index += 1) {
          if (token !== runToken.current) return;
          setActiveStep(index);
          await new Promise((resolve) => window.setTimeout(resolve, 120));
        }
      }
    } catch (error) {
      setRuntimeState(expectsAwsRuntime() ? "error" : "preview");
      setCorrectionError(error instanceof Error ? error.message : "The live run failed.");
    }
    if (token !== runToken.current) return;
    setActiveStep(traceSteps.length);
    setRunState("complete");
  };

  const teachAgent = async () => {
    setTeaching(true);
    setCorrectionError(null);

    try {
      if (runtimeState === "live") {
        if (!threadId || !reviewSummary) {
          throw new Error("Run a human-review case before resuming it.");
        }
        const response = await resumeHumanReview(threadId, (event) => {
          setStreamEvents((current) => [...current, event]);
        });
        setCorrectionId(response.correction_id ?? null);
        setLiveRun(response.result);
      }
      setLearned(true);
      setRunState("idle");
      setActiveStep(0);
      window.setTimeout(() => {
        document.getElementById("case-workbench")?.scrollIntoView({
          behavior: "smooth",
          block: "start",
        });
      }, 40);
    } catch {
      setRuntimeState(expectsAwsRuntime() ? "error" : "preview");
      setCorrectionError("The correction could not be stored. Please run the case and try again.");
    } finally {
      setTeaching(false);
    }
  };

  const runLab = async (title: string, operation: () => Promise<unknown>) => {
    setLabBusy(title);
    setLabResult("");
    try {
      const result = await operation();
      setLabResult(JSON.stringify(result, null, 2));
      fetchEnvelope()
        .then(setEnvelopeRows)
        .catch(() => undefined);
    } catch (error) {
      setLabResult(error instanceof Error ? error.message : "Experiment failed");
    } finally {
      setLabBusy(null);
    }
  };

  const currentDecision: DisplayDecision =
    liveRun?.permission.mode ??
    (learned && demoCase.id === "learning" ? "VERIFY" : demoCase.decision);

  return (
    <main id="top">
      <Header runtimeState={runtimeState} />
      <section className="workbench" id="case-workbench">
        <div className="workbench-heading">
          <div>
            <span className="section-number">Evidence-based resolution operations</span>
            <h1>Evidence-to-action workspace</h1>
          </div>
          <p>
            See what the customer needs, which records are trusted, why permission is granted or
            withheld, and exactly what the agent executes—all in one decision record.
          </p>
        </div>
        <QueueSummary />
        <div className="operations-layout">
          <ScenarioNav
            items={visibleCases}
            selected={selectedId}
            segment={caseSegment}
            onSegment={chooseSegment}
            onSelect={chooseCase}
          />
          <div className="case-workspace">
            <div className="scenario-summary">
              <div>
                <span>
                  Selected case · {demoCase.caseId} · {demoCase.eyebrow}
                </span>
                <h3>{demoCase.title}</h3>
              </div>
              <label className="memory-toggle">
                <input
                  type="checkbox"
                  checked={memoryEnabled}
                  onChange={(event) => setMemoryEnabled(event.target.checked)}
                />
                Experience memory {memoryEnabled ? "on" : "off"}
              </label>
              <button
                type="button"
                className="run-button"
                onClick={runCase}
                disabled={runState === "running"}
              >
                {runState === "running" ? (
                  <>
                    <span className="spinner" /> Evaluating evidence
                  </>
                ) : runState === "complete" ? (
                  <>
                    <Icon name="check" /> Run again
                  </>
                ) : (
                  <>
                    Analyze & resolve <Icon name="arrow" />
                  </>
                )}
              </button>
            </div>
            <DecisionPath
              runState={runState}
              memoryEnabled={memoryEnabled}
              run={liveRun}
              reviewSummary={reviewSummary}
            />
            <AnalystCaseFile demoCase={demoCase} record={catalogCase} run={liveRun} />
            <McpVerificationPanel run={liveRun} />
            <ContainmentProofPanel run={liveRun} />
            <div className="control-grid">
              <div className="control-left">
                <CaseCard demoCase={demoCase} learned={learned} run={liveRun} />
                <MemoryCard demoCase={demoCase} learned={learned} run={liveRun} />
              </div>
              <GateCard demoCase={demoCase} runState={runState} learned={learned} run={liveRun} />
            </div>
            <CounterfactualPanel run={liveRun} />
            <CorrectionPanel
              demoCase={demoCase}
              learned={learned}
              correctionId={correctionId}
              reviewSummary={reviewSummary}
              canTeach={
                runtimeState === "preview" ||
                runtimeState === "error" ||
                Boolean(threadId && reviewSummary)
              }
              teaching={teaching}
              error={correctionError}
              onTeach={teachAgent}
            />
            <WorkflowPanel run={liveRun} reviewSummary={reviewSummary} demoCase={demoCase} />
            <div className="detail-grid">
              <TracePanel
                runState={runState}
                activeStep={activeStep}
                demoCase={demoCase}
                learned={learned}
                events={streamEvents}
              />
              <EvidencePanel demoCase={demoCase} run={liveRun} />
            </div>
            <div
              className={`execution-banner mode-${currentDecision.toLowerCase()} ${runState === "complete" ? "visible" : ""}`}
            >
              <span className="execution-icon">
                <Icon
                  name={
                    currentDecision === "AUTO"
                      ? "check"
                      : currentDecision === "VERIFY"
                        ? "shield"
                        : "user"
                  }
                />
              </span>
              <div>
                <span>Permission result</span>
                <strong>
                  {liveRun?.execution
                    ? `${liveRun.execution.workflow_name} executed and verified · ${liveRun.execution.steps.length} operations · ${money.format(liveRun.execution.executed_amount)}`
                    : currentDecision === "AUTO"
                      ? `${(liveRun?.proposal.action_type ?? demoCase.actionType).replaceAll("_", " ")} executed and verified · ${money.format(liveRun?.execution?.executed_amount ?? demoCase.proposedAmount)}`
                      : currentDecision === "VERIFY"
                        ? "Evidence-qualified plan ready for customer or analyst confirmation"
                        : currentDecision === "DENY"
                          ? "Requested action denied with an evidence-based appeal path"
                          : "Action withheld; prefilled review request created"}
                </strong>
                <small className="runtime-proof">
                  {liveRun
                    ? `Persisted episode ${liveRun.run_id} · ${liveRun.permission.policy_version}`
                    : runtimeState === "live"
                      ? expectsAwsRuntime()
                        ? "Connected to production services"
                        : "Connected to the decision runtime"
                      : runtimeState === "error"
                        ? "Runtime request failed — cached case snapshot shown"
                        : "Case snapshot"}
                </small>
              </div>
              <DecisionBadge decision={currentDecision} />
            </div>
            <ReliabilityLab
              live={runtimeState === "live"}
              run={liveRun}
              busy={labBusy}
              result={labResult}
              onAblation={() =>
                void runLab("Memory ablation", () => runMemoryAblation(demoCase, learned))
              }
              onIdempotency={() =>
                void runLab("Retry safety", () => injectRepeatedRequest(cases[2]))
              }
              onChargeback={() =>
                void runLab("Delayed outcome", () => {
                  if (!liveRun) throw new Error("Run a case first.");
                  return simulateDelayedOutcome(liveRun);
                })
              }
              onPolicyCompare={() =>
                void runLab("Policy v4.9 ↔ v5.0", () => comparePolicyVersions(demoCase, learned))
              }
              onReceipt={() =>
                void runLab("Evidence receipt", async () => {
                  if (!liveRun) throw new Error("Run a case first.");
                  await downloadEvidenceReceipt(liveRun.run_id);
                  return { downloaded: true, episode_id: liveRun.run_id };
                })
              }
              onCorruptHash={() =>
                void runLab("Corrupt evidence hash", () =>
                  simulateEvidenceFault(demoCase.caseId, "corrupt_hash"),
                )
              }
              onStaleRecord={() =>
                void runLab("Expire source record", () =>
                  simulateEvidenceFault(demoCase.caseId, "stale_record"),
                )
              }
              onMismatchCorrelation={() =>
                void runLab("Break entity match", () =>
                  simulateEvidenceFault(demoCase.caseId, "mismatch_correlation"),
                )
              }
            />
          </div>
        </div>
      </section>

      <EnvelopeSection liveRows={envelopeRows} impact={impactSummary} ledger={autonomyLedger} />
      <Footer />
    </main>
  );
}
