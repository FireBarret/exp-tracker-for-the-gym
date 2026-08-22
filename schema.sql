CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS splits (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE       -- 'Push 1', 'Push 2', 'Legs 1', 'Legs 2', 'Pull 1', 'Pull 2'
);

CREATE TABLE IF NOT EXISTS exercises (
  id INTEGER PRIMARY KEY,
  split_id INTEGER NOT NULL REFERENCES splits(id),
  muscle_group TEXT NOT NULL,     -- e.g. 'Chest', 'Shoulders', 'Triceps'
  name TEXT NOT NULL,
  target_sets INTEGER,
  target_rep_range TEXT,          -- e.g. '8-12'
  step_kg REAL NOT NULL DEFAULT 2.5,
  sort_order INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS sessions (
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id),
  split_id INTEGER NOT NULL REFERENCES splits(id),
  date TEXT NOT NULL,             -- ISO date, defaults to today
  notes TEXT                       -- free-text abs/cardio notes (v1)
);

CREATE TABLE IF NOT EXISTS sets (
  id INTEGER PRIMARY KEY,
  session_id INTEGER NOT NULL REFERENCES sessions(id),
  exercise_id INTEGER NOT NULL REFERENCES exercises(id),
  set_number INTEGER NOT NULL,
  weight_kg REAL,                 -- nullable: bodyweight-only sets
  reps INTEGER NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_exercises_split ON exercises(split_id);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sets_session ON sets(session_id);
CREATE INDEX IF NOT EXISTS idx_sets_exercise ON sets(exercise_id);
