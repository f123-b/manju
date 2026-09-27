-- Story Engine V1: structured development, story beats, generation segments and deterministic quality gates.
CREATE TABLE IF NOT EXISTS story_beats (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  episode_id TEXT NOT NULL REFERENCES episodes(id) ON DELETE CASCADE,
  order_index INTEGER NOT NULL,
  beat_type TEXT NOT NULL DEFAULT '',
  weight TEXT NOT NULL DEFAULT 'minor',
  setup TEXT NOT NULL DEFAULT '',
  payoff TEXT NOT NULL DEFAULT '',
  metadata_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(episode_id, order_index)
);

CREATE TABLE IF NOT EXISTS generation_segments (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  episode_id TEXT NOT NULL REFERENCES episodes(id) ON DELETE CASCADE,
  scene_id TEXT NOT NULL REFERENCES scenes(id) ON DELETE CASCADE,
  order_index INTEGER NOT NULL,
  blocking TEXT NOT NULL DEFAULT '',
  soundscape TEXT NOT NULL DEFAULT '',
  music TEXT NOT NULL DEFAULT '',
  video_prompt TEXT NOT NULL DEFAULT '',
  duration_seconds REAL NOT NULL DEFAULT 0,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(scene_id, order_index)
);

CREATE TABLE IF NOT EXISTS story_quality_runs (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  score REAL NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'warning',
  result_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_story_beats_episode ON story_beats(episode_id, order_index);
CREATE INDEX IF NOT EXISTS idx_generation_segments_scene ON generation_segments(scene_id, order_index);
CREATE INDEX IF NOT EXISTS idx_story_quality_project ON story_quality_runs(project_id, created_at);
