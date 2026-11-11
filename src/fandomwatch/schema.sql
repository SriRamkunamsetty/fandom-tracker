-- Enterprise DDL Schema: FandomWatch
-- One template, two dialects ({PK} substituted in db.py). Timestamps are ISO-8601 UTC text.

CREATE TABLE IF NOT EXISTS titles (
  id {PK},
  name TEXT NOT NULL UNIQUE,
  genre TEXT,
  studio TEXT,
  release_date TEXT
);

CREATE TABLE IF NOT EXISTS ingest_runs (
  id {PK},
  source TEXT NOT NULL,
  started_at TEXT NOT NULL,
  status TEXT NOT NULL,
  rows_ok INTEGER NOT NULL DEFAULT 0,
  rows_rejected INTEGER NOT NULL DEFAULT 0,
  quota_units INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS comments (
  id {PK},
  title_id BIGINT NOT NULL REFERENCES titles(id),
  platform TEXT NOT NULL,
  native_id TEXT NOT NULL,
  posted_at TEXT NOT NULL,
  text TEXT NOT NULL,
  likes BIGINT NOT NULL DEFAULT 0,
  is_sample INTEGER NOT NULL DEFAULT 0,
  embedding_json TEXT,
  UNIQUE (platform, native_id)
);

CREATE INDEX IF NOT EXISTS idx_comments_title_time ON comments (title_id, posted_at);
CREATE INDEX IF NOT EXISTS idx_comments_platform ON comments (platform);

CREATE TABLE IF NOT EXISTS backlash_incidents (
  id {PK},
  title_id BIGINT NOT NULL REFERENCES titles(id),
  severity TEXT NOT NULL,
  start_date TEXT NOT NULL,
  end_date TEXT NOT NULL,
  peak_day TEXT NOT NULL,
  peak_neg_share REAL NOT NULL,
  neg_comments INTEGER NOT NULL,
  top_aspects TEXT NOT NULL,
  themes_json TEXT,
  ai_crisis_brief TEXT,
  status TEXT NOT NULL DEFAULT 'open',
  created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_backlash_title ON backlash_incidents (title_id, status);

CREATE TABLE IF NOT EXISTS model_metrics (
  id {PK},
  model_name TEXT NOT NULL,
  metric_name TEXT NOT NULL,
  metric_value REAL NOT NULL,
  dataset_version TEXT,
  measured_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_model_metrics ON model_metrics (model_name, measured_at);
