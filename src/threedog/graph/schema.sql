CREATE TABLE IF NOT EXISTS files(
  id INTEGER PRIMARY KEY,
  path TEXT UNIQUE NOT NULL,
  name TEXT NOT NULL,
  ext TEXT NOT NULL DEFAULT '',
  size INTEGER NOT NULL,
  mtime REAL NOT NULL,
  first_seen TEXT NOT NULL,
  last_seen TEXT NOT NULL,
  deleted INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS file_facts(
  file_id INTEGER PRIMARY KEY REFERENCES files(id) ON DELETE CASCADE,
  summary TEXT NOT NULL DEFAULT '',
  keywords TEXT NOT NULL DEFAULT '[]',
  extracted_at TEXT
);
CREATE TABLE IF NOT EXISTS categories(
  id INTEGER PRIMARY KEY,
  parent_id INTEGER REFERENCES categories(id),
  style_id INTEGER NOT NULL,
  name_raw TEXT NOT NULL,
  path_raw TEXT NOT NULL,
  sort INTEGER NOT NULL DEFAULT 0,
  narration TEXT,
  UNIQUE(style_id, path_raw)
);
CREATE TABLE IF NOT EXISTS assignments(
  id INTEGER PRIMARY KEY,
  file_id INTEGER NOT NULL REFERENCES files(id),
  category_id INTEGER REFERENCES categories(id),
  batch_id TEXT NOT NULL,
  strategy TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'active',
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS style_profiles(
  id INTEGER PRIMARY KEY,
  name TEXT UNIQUE NOT NULL,
  structure TEXT NOT NULL,
  options TEXT NOT NULL,
  naming TEXT NOT NULL,
  presentation TEXT NOT NULL,
  active INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS batches(
  id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  plan_json TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'proposed'
);
CREATE TABLE IF NOT EXISTS journal(
  id INTEGER PRIMARY KEY,
  batch_id TEXT NOT NULL,
  seq INTEGER NOT NULL,
  action TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'done',
  created_at TEXT NOT NULL
);
CREATE VIRTUAL TABLE IF NOT EXISTS file_search USING fts5(name, summary, keywords);
