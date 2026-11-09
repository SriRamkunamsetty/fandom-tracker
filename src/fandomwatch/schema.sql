-- One template, two dialects ({PK} is substituted in db.py). Timestamps are ISO-8601 UTC text.
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
  UNIQUE (platform, native_id)
);
CREATE INDEX IF NOT EXISTS idx_comments_title_time ON comments (title_id, posted_at);
