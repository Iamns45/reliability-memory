-- Create a least-privilege runtime role. Run as a CockroachDB administrator and
-- set the password through your secret manager; never commit it to this file.

CREATE ROLE IF NOT EXISTS reliability_runtime NOLOGIN;

GRANT SELECT, INSERT, UPDATE ON TABLE customers TO reliability_runtime;
GRANT SELECT, INSERT ON TABLE customer_events TO reliability_runtime;
GRANT SELECT ON TABLE policies TO reliability_runtime;
GRANT SELECT, INSERT, UPDATE ON TABLE episodes TO reliability_runtime;
GRANT SELECT, INSERT ON TABLE outcomes TO reliability_runtime;
GRANT SELECT, INSERT, UPDATE ON TABLE human_corrections TO reliability_runtime;
GRANT SELECT, INSERT, UPDATE ON TABLE approvals TO reliability_runtime;
GRANT SELECT, INSERT ON TABLE audit_events TO reliability_runtime;
GRANT SELECT ON TABLE skill_reliability TO reliability_runtime;

-- The CockroachDB Cloud Managed MCP connection used during operations should be
-- scoped to the target cluster and begin read-only. OAuth is preferred.
