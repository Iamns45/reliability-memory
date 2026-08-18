-- Reliability Memory · CockroachDB 25.4+
-- Structured operational state and semantic memory live in one transactionally
-- consistent system of record. Titan v2 embeddings are normalized to 1024d.

CREATE TABLE IF NOT EXISTS customers (
  customer_id STRING PRIMARY KEY,
  display_name STRING NOT NULL,
  account_type STRING NOT NULL CHECK (account_type IN ('standard', 'premium', 'enterprise', 'education')),
  region STRING NOT NULL,
  contract_type STRING NOT NULL DEFAULT 'standard',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  metadata JSONB NOT NULL DEFAULT '{}'::JSONB
);

CREATE TABLE IF NOT EXISTS customer_events (
  event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  customer_id STRING NOT NULL REFERENCES customers (customer_id),
  event_type STRING NOT NULL,
  event_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  data JSONB NOT NULL DEFAULT '{}'::JSONB,
  source STRING NOT NULL DEFAULT 'simulator',
  INDEX customer_timeline_idx (customer_id, event_at DESC)
);

CREATE TABLE IF NOT EXISTS policies (
  policy_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  task_type STRING NOT NULL,
  version STRING NOT NULL,
  rules JSONB NOT NULL,
  valid_from TIMESTAMPTZ NOT NULL,
  valid_until TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (task_type, version)
);

CREATE TABLE IF NOT EXISTS episodes (
  episode_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  agent_id STRING NOT NULL,
  customer_id STRING REFERENCES customers (customer_id),
  task_type STRING NOT NULL,
  summary STRING NOT NULL,
  context JSONB NOT NULL,
  proposed_action JSONB NOT NULL,
  executed_action JSONB,
  risk_level STRING NOT NULL CHECK (risk_level IN ('LOW', 'MEDIUM', 'HIGH')),
  autonomy_decision STRING NOT NULL CHECK (autonomy_decision IN ('AUTO', 'VERIFY', 'HUMAN', 'DENY')),
  policy_version STRING NOT NULL,
  outcome_status STRING NOT NULL CHECK (outcome_status IN ('PENDING', 'VERIFIED_SUCCESS', 'VERIFIED_FAILURE', 'HUMAN_CORRECTED')),
  immediate_outcome JSONB,
  delayed_outcome JSONB,
  verified_success BOOL,
  verification_quality STRING,
  idempotency_key STRING NOT NULL UNIQUE,
  embedding VECTOR(1024),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  verified_at TIMESTAMPTZ,
  INDEX episodes_task_time_idx (task_type, created_at DESC),
  INDEX episodes_customer_time_idx (customer_id, created_at DESC),
  INDEX episodes_outcome_idx (task_type, outcome_status, verified_at DESC)
);

-- Prefixing by task type keeps semantically unrelated memories out of the
-- candidate set. Normalized Titan embeddings make L2 suitable for retrieval.
CREATE VECTOR INDEX IF NOT EXISTS episodes_memory_vector_idx
ON episodes (task_type, embedding);

CREATE TABLE IF NOT EXISTS outcomes (
  outcome_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  episode_id UUID NOT NULL REFERENCES episodes (episode_id),
  outcome_type STRING NOT NULL CHECK (outcome_type IN ('immediate', 'delayed')),
  data JSONB NOT NULL,
  verified BOOL NOT NULL DEFAULT false,
  verifier STRING NOT NULL DEFAULT 'deterministic-simulator-v1',
  observed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (episode_id, outcome_type)
);

CREATE TABLE IF NOT EXISTS human_corrections (
  correction_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  episode_id UUID NOT NULL UNIQUE REFERENCES episodes (episode_id),
  task_type STRING NOT NULL,
  agent_proposal JSONB NOT NULL,
  human_action JSONB NOT NULL,
  reason STRING NOT NULL,
  lesson STRING NOT NULL,
  reviewer_id STRING NOT NULL DEFAULT 'demo-reviewer',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  embedding VECTOR(1024)
);

CREATE VECTOR INDEX IF NOT EXISTS corrections_task_memory_vector_idx
ON human_corrections (task_type, embedding);

CREATE TABLE IF NOT EXISTS approvals (
  approval_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  episode_id UUID NOT NULL UNIQUE REFERENCES episodes (episode_id),
  status STRING NOT NULL CHECK (status IN ('PENDING', 'APPROVED', 'REJECTED', 'CORRECTED')),
  reviewer_id STRING,
  reviewer_reason STRING,
  proposed_action JSONB NOT NULL,
  resolved_action JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  resolved_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS audit_events (
  audit_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  episode_id UUID REFERENCES episodes (episode_id),
  actor_type STRING NOT NULL CHECK (actor_type IN ('agent', 'policy', 'human', 'verifier', 'system')),
  event_type STRING NOT NULL,
  payload JSONB NOT NULL DEFAULT '{}'::JSONB,
  event_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  INDEX audit_episode_time_idx (episode_id, event_at)
);

CREATE OR REPLACE VIEW skill_reliability AS
SELECT
  agent_id,
  task_type,
  count(*) FILTER (WHERE outcome_status != 'PENDING') AS verified_cases,
  count(*) FILTER (WHERE outcome_status = 'VERIFIED_SUCCESS') AS successes,
  count(*) FILTER (WHERE outcome_status = 'VERIFIED_FAILURE') AS failures,
  count(*) FILTER (WHERE outcome_status = 'HUMAN_CORRECTED') AS human_overrides,
  max(verified_at) AS last_verified_at
FROM episodes
GROUP BY agent_id, task_type;
