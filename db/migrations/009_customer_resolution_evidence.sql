-- Generalize the analyst queue from one refund pattern to issue-specific
-- customer resolution evidence. The sparse source packet stays JSONB because
-- delivery, device, quality, warranty, seller, and recovery systems expose
-- different fields; every source retains a stable key and provenance label.

ALTER TABLE analyst_cases
ADD COLUMN IF NOT EXISTS evidence_bundle JSONB NOT NULL DEFAULT '{}'::JSONB;

CREATE INDEX IF NOT EXISTS analyst_cases_task_priority_idx
ON analyst_cases (task_type, priority, created_at DESC);

GRANT SELECT ON TABLE analyst_cases TO reliability_runtime;

UPSERT INTO policies (task_type, version, rules, valid_from) VALUES (
  'customer_resolution',
  'customer-resolution-v5.0',
  '{"order":["current_case_eligibility","hard_safety_and_identity_rules","scenario_floor","verified_reliability","bounded_company_cost"],"permissions":["AUTO","VERIFY","HUMAN","DENY"],"model_may_authorize":false}',
  now()
);
