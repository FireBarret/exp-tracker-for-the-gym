"""One-shot deploy helper: creates gym.db from schema.sql, then seeds it.

Run once after first deploy (local or PythonAnywhere):
    python init_db.py

Safe to re-run any time -- schema uses CREATE TABLE IF NOT EXISTS and seed.py
skips rows that already exist.
"""
from models import get_db, init_schema
from seed import seed

if __name__ == "__main__":
    init_schema()
    conn = get_db()
    seed(conn)
    conn.close()
    print("Database initialized and seeded (gym.db).")
