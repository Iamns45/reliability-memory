CREATE TABLE IF NOT EXISTS mcp_verification_receipts (
    receipt_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    episode_id UUID NOT NULL UNIQUE REFERENCES episodes (episode_id) ON DELETE CASCADE,
    provider STRING NOT NULL,
    endpoint STRING NOT NULL,
    cluster_scope STRING NOT NULL,
    database_name STRING NOT NULL,
    tool_name STRING NOT NULL,
    required BOOL NOT NULL,
    verified BOOL NOT NULL,
    observed_episode_id STRING NULL,
    observed_decision STRING NULL,
    observed_policy_version STRING NULL,
    vector_check_performed BOOL NOT NULL,
    expected_neighbor_ids JSONB NOT NULL DEFAULT '[]'::JSONB,
    vector_neighbor_ids JSONB NOT NULL DEFAULT '[]'::JSONB,
    matching_neighbor_ids JSONB NOT NULL DEFAULT '[]'::JSONB,
    receipt_hash STRING NOT NULL,
    failure_reason STRING NULL,
    checked_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT mcp_receipt_hash_length CHECK (length(receipt_hash) = 64)
);

CREATE INDEX IF NOT EXISTS mcp_verification_status_idx
    ON mcp_verification_receipts (verified, checked_at DESC);

CREATE INDEX IF NOT EXISTS mcp_verification_cluster_idx
    ON mcp_verification_receipts (cluster_scope, checked_at DESC);
