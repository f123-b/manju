CREATE TABLE IF NOT EXISTS schema_migrations (
  version TEXT PRIMARY KEY,
  applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS projects (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT '策划中',
  format TEXT NOT NULL DEFAULT '16:9',
  target_episodes INTEGER NOT NULL DEFAULT 1,
  current_episode_id TEXT,
  due_date TEXT,
  budget REAL NOT NULL DEFAULT 0,
  spent REAL NOT NULL DEFAULT 0,
  generated_shots INTEGER NOT NULL DEFAULT 0,
  total_shots INTEGER NOT NULL DEFAULT 0,
  qc_score REAL NOT NULL DEFAULT 0,
  archived INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS story_bibles (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL UNIQUE REFERENCES projects(id) ON DELETE CASCADE,
  logline TEXT NOT NULL DEFAULT '',
  core_conflict TEXT NOT NULL DEFAULT '',
  main_line TEXT NOT NULL DEFAULT '',
  theme TEXT NOT NULL DEFAULT '',
  ending TEXT NOT NULL DEFAULT '',
  world TEXT NOT NULL DEFAULT '',
  style TEXT NOT NULL DEFAULT '',
  rules_json TEXT NOT NULL DEFAULT '[]',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS episodes (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  order_index INTEGER NOT NULL,
  title TEXT NOT NULL,
  summary TEXT NOT NULL DEFAULT '',
  opening_hook TEXT NOT NULL DEFAULT '',
  core_event TEXT NOT NULL DEFAULT '',
  payoff TEXT NOT NULL DEFAULT '',
  twist TEXT NOT NULL DEFAULT '',
  ending_hook TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT '待策划',
  duration TEXT NOT NULL DEFAULT '--:--',
  locked INTEGER NOT NULL DEFAULT 0,
  archived INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(project_id, order_index)
);

CREATE TABLE IF NOT EXISTS locations (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  meta TEXT NOT NULL DEFAULT '',
  description TEXT NOT NULL DEFAULT '',
  image TEXT,
  status TEXT NOT NULL DEFAULT '待确认',
  archived INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS characters (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  age TEXT NOT NULL DEFAULT '',
  gender TEXT NOT NULL DEFAULT '',
  role TEXT NOT NULL DEFAULT '',
  appearance TEXT NOT NULL DEFAULT '',
  personality TEXT NOT NULL DEFAULT '',
  voice_profile TEXT NOT NULL DEFAULT '',
  prompt TEXT NOT NULL DEFAULT '',
  negative_prompt TEXT NOT NULL DEFAULT '',
  meta TEXT NOT NULL DEFAULT '',
  image TEXT,
  status TEXT NOT NULL DEFAULT '待确认',
  archived INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS character_outfits (
  id TEXT PRIMARY KEY,
  character_id TEXT NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  reference_asset_id TEXT,
  prompt TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT '待确认',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS props (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  meta TEXT NOT NULL DEFAULT '',
  description TEXT NOT NULL DEFAULT '',
  image TEXT,
  status TEXT NOT NULL DEFAULT '待确认',
  archived INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS scenes (
  id TEXT PRIMARY KEY,
  episode_id TEXT NOT NULL REFERENCES episodes(id) ON DELETE CASCADE,
  order_index INTEGER NOT NULL,
  title TEXT NOT NULL,
  location_id TEXT REFERENCES locations(id) ON DELETE SET NULL,
  time_of_day TEXT NOT NULL DEFAULT '',
  purpose TEXT NOT NULL DEFAULT '',
  emotion_start TEXT NOT NULL DEFAULT '',
  emotion_end TEXT NOT NULL DEFAULT '',
  summary TEXT NOT NULL DEFAULT '',
  estimated_duration INTEGER NOT NULL DEFAULT 0,
  script_json TEXT NOT NULL DEFAULT '{}',
  archived INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(episode_id, order_index)
);

CREATE TABLE IF NOT EXISTS shots (
  id TEXT PRIMARY KEY,
  scene_id TEXT NOT NULL REFERENCES scenes(id) ON DELETE CASCADE,
  order_index INTEGER NOT NULL,
  timecode TEXT NOT NULL DEFAULT '',
  description TEXT NOT NULL DEFAULT '',
  shot_size TEXT NOT NULL DEFAULT '',
  frame TEXT NOT NULL DEFAULT '16:9（横屏）',
  camera_angle TEXT NOT NULL DEFAULT '',
  lens TEXT NOT NULL DEFAULT '',
  movement TEXT NOT NULL DEFAULT '',
  duration INTEGER NOT NULL DEFAULT 4,
  action TEXT NOT NULL DEFAULT '',
  emotion TEXT NOT NULL DEFAULT '',
  dialogue TEXT NOT NULL DEFAULT '',
  prompt TEXT NOT NULL DEFAULT '',
  negative_prompt TEXT NOT NULL DEFAULT '',
  image TEXT,
  status TEXT NOT NULL DEFAULT '待生成',
  reviewed INTEGER NOT NULL DEFAULT 0,
  qc_score REAL,
  cost REAL NOT NULL DEFAULT 0,
  archived INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(scene_id, order_index)
);

CREATE TABLE IF NOT EXISTS scene_characters (
  scene_id TEXT NOT NULL REFERENCES scenes(id) ON DELETE CASCADE,
  character_id TEXT NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
  outfit_id TEXT REFERENCES character_outfits(id) ON DELETE SET NULL,
  PRIMARY KEY(scene_id, character_id)
);

CREATE TABLE IF NOT EXISTS shot_characters (
  shot_id TEXT NOT NULL REFERENCES shots(id) ON DELETE CASCADE,
  character_id TEXT NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
  outfit_id TEXT REFERENCES character_outfits(id) ON DELETE SET NULL,
  PRIMARY KEY(shot_id, character_id)
);

CREATE TABLE IF NOT EXISTS shot_props (
  shot_id TEXT NOT NULL REFERENCES shots(id) ON DELETE CASCADE,
  prop_id TEXT NOT NULL REFERENCES props(id) ON DELETE CASCADE,
  PRIMARY KEY(shot_id, prop_id)
);

CREATE TABLE IF NOT EXISTS media_assets (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  type TEXT NOT NULL,
  path_or_url TEXT NOT NULL,
  source TEXT NOT NULL DEFAULT 'generated',
  provider TEXT,
  model TEXT,
  prompt TEXT,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS generation_tasks (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  shot_id TEXT NOT NULL REFERENCES shots(id) ON DELETE CASCADE,
  type TEXT NOT NULL DEFAULT '视频',
  provider TEXT NOT NULL,
  model TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'Queued',
  prompt TEXT NOT NULL DEFAULT '',
  parameters_json TEXT NOT NULL DEFAULT '{}',
  estimated_cost REAL NOT NULL DEFAULT 0,
  actual_cost REAL,
  progress INTEGER NOT NULL DEFAULT 0,
  retry_count INTEGER NOT NULL DEFAULT 0,
  max_retries INTEGER NOT NULL DEFAULT 3,
  error_message TEXT,
  provider_task_id TEXT,
  status_url TEXT,
  queued_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  started_at TEXT,
  completed_at TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS generation_versions (
  id TEXT PRIMARY KEY,
  shot_id TEXT NOT NULL REFERENCES shots(id) ON DELETE CASCADE,
  parent_version_id TEXT REFERENCES generation_versions(id) ON DELETE SET NULL,
  version_number INTEGER NOT NULL,
  media_asset_id TEXT REFERENCES media_assets(id) ON DELETE SET NULL,
  provider TEXT NOT NULL,
  model TEXT NOT NULL,
  prompt_snapshot TEXT NOT NULL DEFAULT '',
  negative_prompt_snapshot TEXT NOT NULL DEFAULT '',
  parameters_json TEXT NOT NULL DEFAULT '{}',
  reference_assets_json TEXT NOT NULL DEFAULT '[]',
  estimated_cost REAL NOT NULL DEFAULT 0,
  actual_cost REAL,
  qc_score REAL,
  is_active INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(shot_id, version_number)
);

CREATE TABLE IF NOT EXISTS cost_records (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  episode_id TEXT REFERENCES episodes(id) ON DELETE SET NULL,
  scene_id TEXT REFERENCES scenes(id) ON DELETE SET NULL,
  shot_id TEXT REFERENCES shots(id) ON DELETE SET NULL,
  task_id TEXT REFERENCES generation_tasks(id) ON DELETE SET NULL,
  provider TEXT NOT NULL,
  model TEXT NOT NULL,
  category TEXT NOT NULL,
  estimated_cost REAL NOT NULL DEFAULT 0,
  actual_cost REAL NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'estimated',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS qc_records (
  id TEXT PRIMARY KEY,
  shot_id TEXT NOT NULL REFERENCES shots(id) ON DELETE CASCADE,
  version_id TEXT REFERENCES generation_versions(id) ON DELETE SET NULL,
  type TEXT NOT NULL,
  score REAL,
  severity TEXT NOT NULL DEFAULT 'info',
  message TEXT NOT NULL DEFAULT '',
  metadata_json TEXT NOT NULL DEFAULT '{}',
  status TEXT NOT NULL DEFAULT 'manual_review',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS dependencies (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  source_type TEXT NOT NULL,
  source_id TEXT NOT NULL,
  target_type TEXT NOT NULL,
  target_id TEXT NOT NULL,
  relation TEXT NOT NULL DEFAULT 'affects',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(source_type, source_id, target_type, target_id, relation)
);

CREATE TABLE IF NOT EXISTS export_jobs (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  status TEXT NOT NULL DEFAULT 'Queued',
  output_path TEXT,
  error_message TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  completed_at TEXT
);

CREATE TABLE IF NOT EXISTS model_definitions (
  provider TEXT NOT NULL,
  model_id TEXT NOT NULL,
  display_name TEXT NOT NULL,
  type TEXT NOT NULL,
  enabled INTEGER NOT NULL DEFAULT 1,
  pricing_json TEXT NOT NULL DEFAULT '{}',
  capabilities_json TEXT NOT NULL DEFAULT '{}',
  metadata_json TEXT NOT NULL DEFAULT '{}',
  PRIMARY KEY(provider, model_id)
);

CREATE INDEX IF NOT EXISTS idx_episodes_project ON episodes(project_id, order_index);
CREATE INDEX IF NOT EXISTS idx_scenes_episode ON scenes(episode_id, order_index);
CREATE INDEX IF NOT EXISTS idx_shots_scene ON shots(scene_id, order_index);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON generation_tasks(status, queued_at);
CREATE INDEX IF NOT EXISTS idx_cost_project ON cost_records(project_id, created_at);
CREATE INDEX IF NOT EXISTS idx_dependencies_source ON dependencies(source_type, source_id);
