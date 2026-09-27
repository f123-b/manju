-- Audio Engine V1: stable voice identity, line-level performance, immutable takes, QC and timeline clips.
CREATE TABLE IF NOT EXISTS voice_profiles (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  character_id TEXT NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  provider_type TEXT NOT NULL DEFAULT 'mock',
  provider_voice_id TEXT NOT NULL DEFAULT '',
  model_id TEXT NOT NULL DEFAULT '',
  language TEXT NOT NULL DEFAULT 'zh-CN',
  accent TEXT NOT NULL DEFAULT '',
  base_style TEXT NOT NULL DEFAULT '',
  reference_audio_asset_id TEXT REFERENCES media_assets(id) ON DELETE SET NULL,
  reference_text TEXT NOT NULL DEFAULT '',
  embedding_ref TEXT NOT NULL DEFAULT '',
  metadata_json TEXT NOT NULL DEFAULT '{}',
  consent_status TEXT NOT NULL DEFAULT 'unknown',
  is_locked INTEGER NOT NULL DEFAULT 0,
  locked_at TEXT,
  is_default INTEGER NOT NULL DEFAULT 0,
  source TEXT NOT NULL DEFAULT 'migrated',
  owner_note TEXT NOT NULL DEFAULT '',
  approval_at TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS dialogue_lines (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  episode_id TEXT REFERENCES episodes(id) ON DELETE CASCADE,
  scene_id TEXT REFERENCES scenes(id) ON DELETE CASCADE,
  shot_id TEXT REFERENCES shots(id) ON DELETE SET NULL,
  character_id TEXT REFERENCES characters(id) ON DELETE SET NULL,
  order_index INTEGER NOT NULL DEFAULT 0,
  text TEXT NOT NULL DEFAULT '',
  language TEXT NOT NULL DEFAULT 'zh-CN',
  start_offset_ms INTEGER NOT NULL DEFAULT 0,
  target_duration_ms INTEGER,
  voice_profile_id TEXT REFERENCES voice_profiles(id) ON DELETE SET NULL,
  pronunciation_overrides_json TEXT NOT NULL DEFAULT '{}',
  status TEXT NOT NULL DEFAULT 'draft',
  stale INTEGER NOT NULL DEFAULT 0,
  stale_reason TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS voice_performances (
  dialogue_line_id TEXT PRIMARY KEY REFERENCES dialogue_lines(id) ON DELETE CASCADE,
  emotion TEXT NOT NULL DEFAULT 'neutral',
  emotion_intensity REAL NOT NULL DEFAULT 0.5,
  speed REAL NOT NULL DEFAULT 1.0,
  pitch REAL NOT NULL DEFAULT 0.0,
  volume_db REAL NOT NULL DEFAULT 0.0,
  pause_before_ms INTEGER NOT NULL DEFAULT 0,
  pause_after_ms INTEGER NOT NULL DEFAULT 0,
  breath_cues_json TEXT NOT NULL DEFAULT '[]',
  delivery_instruction TEXT NOT NULL DEFAULT '',
  target_duration_ms INTEGER,
  source TEXT NOT NULL DEFAULT 'manual',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS voice_takes (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  dialogue_line_id TEXT NOT NULL REFERENCES dialogue_lines(id) ON DELETE CASCADE,
  generation_task_id TEXT REFERENCES generation_tasks(id) ON DELETE SET NULL,
  media_asset_id TEXT REFERENCES media_assets(id) ON DELETE SET NULL,
  provider TEXT NOT NULL,
  model TEXT NOT NULL,
  voice_profile_snapshot_json TEXT NOT NULL DEFAULT '{}',
  performance_snapshot_json TEXT NOT NULL DEFAULT '{}',
  input_text_snapshot TEXT NOT NULL DEFAULT '',
  reference_audio_snapshot_json TEXT NOT NULL DEFAULT '{}',
  duration_ms INTEGER,
  estimated_cost REAL NOT NULL DEFAULT 0,
  actual_cost REAL,
  qc_score REAL,
  qc_status TEXT NOT NULL DEFAULT 'pending',
  status TEXT NOT NULL DEFAULT 'queued',
  is_active INTEGER NOT NULL DEFAULT 0,
  stale INTEGER NOT NULL DEFAULT 0,
  stale_reason TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS audio_qc_records (
  id TEXT PRIMARY KEY,
  voice_take_id TEXT NOT NULL REFERENCES voice_takes(id) ON DELETE CASCADE,
  check_type TEXT NOT NULL,
  score REAL,
  severity TEXT NOT NULL DEFAULT 'info',
  message TEXT NOT NULL DEFAULT '',
  metadata_json TEXT NOT NULL DEFAULT '{}',
  status TEXT NOT NULL DEFAULT 'manual_review',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS audio_clips (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  episode_id TEXT REFERENCES episodes(id) ON DELETE CASCADE,
  scene_id TEXT REFERENCES scenes(id) ON DELETE CASCADE,
  track_type TEXT NOT NULL DEFAULT 'dialogue',
  media_asset_id TEXT REFERENCES media_assets(id) ON DELETE SET NULL,
  timeline_start_ms INTEGER NOT NULL DEFAULT 0,
  source_start_ms INTEGER NOT NULL DEFAULT 0,
  duration_ms INTEGER NOT NULL DEFAULT 0,
  gain_db REAL NOT NULL DEFAULT 0,
  fade_in_ms INTEGER NOT NULL DEFAULT 0,
  fade_out_ms INTEGER NOT NULL DEFAULT 0,
  linked_dialogue_line_id TEXT REFERENCES dialogue_lines(id) ON DELETE SET NULL,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  stale INTEGER NOT NULL DEFAULT 0,
  stale_reason TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS audio_mixdowns (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  episode_id TEXT REFERENCES episodes(id) ON DELETE CASCADE,
  media_asset_id TEXT REFERENCES media_assets(id) ON DELETE SET NULL,
  status TEXT NOT NULL DEFAULT 'ready',
  duration_ms INTEGER NOT NULL DEFAULT 0,
  loudness_lufs REAL,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS voice_provider_definitions (
  id TEXT PRIMARY KEY,
  provider_type TEXT NOT NULL UNIQUE,
  display_name TEXT NOT NULL,
  endpoint TEXT NOT NULL DEFAULT '',
  enabled INTEGER NOT NULL DEFAULT 1,
  capabilities_json TEXT NOT NULL DEFAULT '{}',
  supported_languages_json TEXT NOT NULL DEFAULT '[]',
  pricing_json TEXT NOT NULL DEFAULT '{}',
  health_state TEXT NOT NULL DEFAULT 'unknown',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_voice_profiles_character ON voice_profiles(character_id, is_default, is_locked);
CREATE INDEX IF NOT EXISTS idx_dialogue_lines_scene ON dialogue_lines(scene_id, order_index);
CREATE INDEX IF NOT EXISTS idx_dialogue_lines_episode ON dialogue_lines(episode_id, order_index);
CREATE INDEX IF NOT EXISTS idx_voice_takes_line ON voice_takes(dialogue_line_id, created_at);
CREATE INDEX IF NOT EXISTS idx_voice_takes_task ON voice_takes(generation_task_id);
CREATE INDEX IF NOT EXISTS idx_audio_qc_take ON audio_qc_records(voice_take_id, created_at);
CREATE INDEX IF NOT EXISTS idx_audio_clips_timeline ON audio_clips(episode_id, track_type, timeline_start_ms);

INSERT OR IGNORE INTO voice_provider_definitions(id, provider_type, display_name, capabilities_json, supported_languages_json)
VALUES
  ('VP-MOCK', 'mock', 'Local WAV Demo', '{"synthesize":true,"health":true}', '["zh-CN","en-US"]'),
  ('VP-COSYVOICE', 'cosyvoice', 'CosyVoice HTTP', '{"synthesize":true,"clone":true,"health":true}', '["zh-CN","en-US"]'),
  ('VP-CHATTERBOX', 'chatterbox', 'Chatterbox HTTP', '{"synthesize":true,"health":true}', '["en-US"]'),
  ('VP-GPTSOVITS', 'gpt-sovits', 'GPT-SoVITS HTTP', '{"synthesize":true,"clone":true,"health":true}', '["zh-CN","ja-JP","en-US"]');
