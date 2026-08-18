-- Track embedding provenance so retrieval never compares vectors produced by
-- different models or input contracts.

ALTER TABLE episodes
ADD COLUMN IF NOT EXISTS embedding_model STRING;

ALTER TABLE episodes
ADD COLUMN IF NOT EXISTS embedding_input_version STRING;

ALTER TABLE episodes
ADD COLUMN IF NOT EXISTS embedded_at TIMESTAMPTZ;

UPDATE episodes
SET embedding_model = CASE
      WHEN context->>'synthetic' = 'true' THEN 'deterministic-seed-sha256-v1'
      ELSE 'legacy-unknown'
    END,
    embedding_input_version = CASE
      WHEN context->>'synthetic' = 'true' THEN 'episode-summary-v1'
      ELSE 'legacy-unknown'
    END,
    embedded_at = COALESCE(verified_at, created_at)
WHERE embedding IS NOT NULL
  AND embedding_model IS NULL;

ALTER TABLE human_corrections
ADD COLUMN IF NOT EXISTS embedding_model STRING;

ALTER TABLE human_corrections
ADD COLUMN IF NOT EXISTS embedding_input_version STRING;

ALTER TABLE human_corrections
ADD COLUMN IF NOT EXISTS embedded_at TIMESTAMPTZ;

UPDATE human_corrections
SET embedding_model = 'legacy-unknown',
    embedding_input_version = 'legacy-unknown',
    embedded_at = created_at
WHERE embedding IS NOT NULL
  AND embedding_model IS NULL;
