-- Review summaries are persisted beside the approval so a reviewer receives a
-- complete decision packet and only needs to confirm or edit the resolution.

ALTER TABLE approvals
ADD COLUMN IF NOT EXISTS review_summary JSONB;

CREATE INDEX IF NOT EXISTS approvals_status_created_idx
ON approvals (status, created_at DESC);

UPSERT INTO policies (task_type, version, rules, valid_from) VALUES
  (
    'duplicate_charge_refund',
    'refund-policy-v4.2',
    '{"auto":{"max_amount":200,"min_reliability":0.95,"min_verified_cases":50,"required_risk":"LOW"},"human":{"amount_over":1000,"custom_sla":true}}',
    now() - INTERVAL '12 months'
  ),
  (
    'education_contract_exception',
    'refund-policy-v4.3',
    '{"verify":{"max_amount":500,"relevant_correction_required":true},"auto":{"enabled":false},"human":{"novel_without_correction":true}}',
    now() - INTERVAL '6 months'
  );
