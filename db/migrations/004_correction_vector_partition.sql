-- Upgrade existing installations so correction vectors are partitioned by task.
-- New installations already receive this shape from 001_reliability_memory.sql.

ALTER TABLE human_corrections
ADD COLUMN IF NOT EXISTS task_type STRING;

UPDATE human_corrections AS correction
SET task_type = episode.task_type
FROM episodes AS episode
WHERE correction.episode_id = episode.episode_id
  AND correction.task_type IS NULL;

ALTER TABLE human_corrections
ALTER COLUMN task_type SET NOT NULL;

CREATE VECTOR INDEX IF NOT EXISTS corrections_task_memory_vector_idx
ON human_corrections (task_type, embedding);
