-- Persistent LibTV-style canvas nodes and directed workflow edges.
CREATE TABLE IF NOT EXISTS canvas_nodes (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  node_type TEXT NOT NULL,
  title TEXT NOT NULL,
  x REAL NOT NULL DEFAULT 120,
  y REAL NOT NULL DEFAULT 120,
  width REAL NOT NULL DEFAULT 280,
  height REAL NOT NULL DEFAULT 180,
  status TEXT NOT NULL DEFAULT 'idle',
  data_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS canvas_edges (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  source_node_id TEXT NOT NULL REFERENCES canvas_nodes(id) ON DELETE CASCADE,
  target_node_id TEXT NOT NULL REFERENCES canvas_nodes(id) ON DELETE CASCADE,
  label TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(source_node_id, target_node_id)
);

CREATE INDEX IF NOT EXISTS idx_canvas_nodes_project ON canvas_nodes(project_id, updated_at);
CREATE INDEX IF NOT EXISTS idx_canvas_edges_project ON canvas_edges(project_id, created_at);
