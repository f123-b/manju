-- Character Asset Engine: stable identity, mutable looks, reviewable references
CREATE TABLE IF NOT EXISTS character_looks (
  id TEXT PRIMARY KEY,
  character_id TEXT NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  base_look_id TEXT REFERENCES character_looks(id) ON DELETE SET NULL,
  description TEXT NOT NULL DEFAULT '',
  wardrobe_json TEXT NOT NULL DEFAULT '{}',
  hair_makeup_json TEXT NOT NULL DEFAULT '{}',
  accessories_json TEXT NOT NULL DEFAULT '{}',
  injuries_json TEXT NOT NULL DEFAULT '{}',
  weathering_json TEXT NOT NULL DEFAULT '{}',
  differences_json TEXT NOT NULL DEFAULT '{}',
  cause_ref TEXT,
  valid_from_scene_id TEXT,
  valid_to_scene_id TEXT,
  status TEXT NOT NULL DEFAULT 'draft',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS character_references (
  id TEXT PRIMARY KEY,
  character_id TEXT NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
  look_id TEXT REFERENCES character_looks(id) ON DELETE SET NULL,
  media_asset_id TEXT REFERENCES media_assets(id) ON DELETE SET NULL,
  reference_type TEXT NOT NULL DEFAULT 'candidate',
  view_angle TEXT NOT NULL DEFAULT 'front',
  quality_level TEXT NOT NULL DEFAULT 'candidate',
  lifecycle_status TEXT NOT NULL DEFAULT 'planned',
  is_primary INTEGER NOT NULL DEFAULT 0,
  source TEXT NOT NULL DEFAULT 'generated',
  generation_version_id TEXT,
  generation_task_id TEXT,
  candidate_group TEXT,
  prompt_snapshot TEXT NOT NULL DEFAULT '',
  quality_score REAL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS continuity_locks (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  scope_type TEXT NOT NULL,
  scope_id TEXT NOT NULL,
  lock_key TEXT NOT NULL,
  value_json TEXT NOT NULL DEFAULT '{}',
  valid_from_scene_id TEXT,
  valid_to_scene_id TEXT,
  source_ref TEXT,
  status TEXT NOT NULL DEFAULT 'active',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(scope_type, scope_id, lock_key, valid_from_scene_id, valid_to_scene_id)
);

CREATE INDEX IF NOT EXISTS idx_character_looks_character ON character_looks(character_id, status);
CREATE INDEX IF NOT EXISTS idx_character_references_character ON character_references(character_id, lifecycle_status, is_primary);
CREATE INDEX IF NOT EXISTS idx_character_references_task ON character_references(generation_task_id);
CREATE INDEX IF NOT EXISTS idx_continuity_locks_scope ON continuity_locks(scope_type, scope_id, status);
