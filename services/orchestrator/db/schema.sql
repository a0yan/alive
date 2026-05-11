CREATE TABLE IF NOT EXISTS audit_log (
  id            SERIAL PRIMARY KEY,
  workflow_id   TEXT NOT NULL,
  anomaly_id    TEXT NOT NULL,
  source        TEXT NOT NULL,
  anomaly_type  TEXT NOT NULL,
  llm_summary   TEXT,
  confidence    FLOAT,
  action_taken  TEXT,
  action_status TEXT,  -- auto_executed | pending_approval | approved | rejected | skipped
  approved_by   TEXT,
  created_at    TIMESTAMPTZ DEFAULT now(),
  resolved_at   TIMESTAMPTZ
);
