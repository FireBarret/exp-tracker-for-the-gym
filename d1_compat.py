"""Sync-looking wrapper around D1, standing in for sqlite3.Connection so every
query function in models.py runs unmodified against D1 (Cloudflare's
serverless SQLite) instead of a local gym.db file.

D1's binding is async (`await stmt.run()`); Flask's view functions are sync.
`run_sync` -- the bridge Cloudflare's own Flask-on-Python-Workers docs use for
this exact situation -- drives the coroutine to completion from inside a
synchronous call, so nothing above this module needs to know it's async.

Verified directly against a local `pywrangler dev` + D1 instance:
- a D1Result behaves like a dict (`result["meta"]["last_row_id"]`) and
  `dict(row)` on a result row returns a plain, JSON-safe Python dict.
- `env.DB.exec(sql)` runs a semicolon-separated script in one call, standing
  in for sqlite3's `executescript`.
- `.bind(...)` passes `None` through to SQL NULL correctly.
"""
from pyodide.ffi import run_sync


class Cursor:
    """Just enough of sqlite3.Cursor for models.py: fetchone/fetchall/lastrowid."""

    def __init__(self, d1_result):
        rows = d1_result["results"] or []
        self._rows = [dict(r) for r in rows]
        self._i = 0
        meta = dict(d1_result["meta"] or {})
        self.lastrowid = meta.get("last_row_id")
        self.rowcount = meta.get("changes", 0)

    def fetchone(self):
        if self._i >= len(self._rows):
            return None
        row = self._rows[self._i]
        self._i += 1
        return row

    def fetchall(self):
        rows = self._rows[self._i:]
        self._i = len(self._rows)
        return rows

    def __iter__(self):
        return iter(self.fetchall())


class D1Connection:
    """Enough of sqlite3.Connection's surface for models.py to run unmodified.

    Note on foreign_keys / transactions: D1 auto-commits every statement, and
    each one may run against a fresh underlying connection, so `PRAGMA
    foreign_keys = ON` and multi-statement atomicity aren't guaranteed the way
    a single sqlite3.Connection gave us. Every cascading delete in models.py
    already deletes children explicitly rather than relying on ON DELETE
    CASCADE, so this doesn't change behavior -- just noting the gap.
    """

    def __init__(self, db_binding):
        self._db = db_binding

    def execute(self, sql, params=()):
        stmt = self._db.prepare(sql)
        if params:
            stmt = stmt.bind(*params)
        return Cursor(run_sync(stmt.run()))

    def executescript(self, script):
        run_sync(self._db.exec(script))
        return Cursor({"results": [], "meta": {}})

    def commit(self):
        pass  # D1 auto-commits every statement; nothing to flush.

    def close(self):
        pass  # No socket/handle to release.
