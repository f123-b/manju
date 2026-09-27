-- Editable picture/video timeline clips. A clip is independent from the shot
-- so a shot can be moved, trimmed, or removed from the episode timeline.
CREATE TABLE IF NOT EXISTS video_clips (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  episode_id TEXT NOT NULL REFERENCES episodes(id) ON DELETE CASCADE,
  scene_id TEXT REFERENCES scenes(id) ON DELETE SET NULL,
  shot_id TEXT NOT NULL REFERENCES shots(id) ON DELETE CASCADE,
  track_type TEXT NOT NULL DEFAULT 'video',
  timeline_start_ms INTEGER NOT NULL DEFAULT 0,
  source_start_ms INTEGER NOT NULL DEFAULT 0,
  duration_ms INTEGER NOT NULL DEFAULT 0,
  transition_json TEXT NOT NULL DEFAULT '{}',
  metadata_json TEXT NOT NULL DEFAULT '{}',
  archived INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(episode_id, shot_id)
);

CREATE INDEX IF NOT EXISTS idx_video_clips_timeline ON video_clips(episode_id, archived, timeline_start_ms);
