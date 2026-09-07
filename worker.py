"""Cloudflare Workers entrypoint.

Flask opens/verifies the session cookie as soon as the WSGI app is called --
before any @app.before_request hook runs -- so app.secret_key has to be set
here, ahead of wsgi.fetch(), rather than inside app.py's request hooks (which
is where GYM_APP_PASSWORD and the D1 connection are wired up instead, since
those are only read *during* request handling).

`wrangler secret put FLASK_SECRET_KEY` / `GYM_APP_PASSWORD` make these
available as attributes on `env`, not as os.environ vars.
"""
from workers import WorkerEntrypoint, wsgi

from app import app


class Default(WorkerEntrypoint):
    async def fetch(self, request):
        app.secret_key = self.env.FLASK_SECRET_KEY
        app.config["GYM_APP_PASSWORD"] = getattr(self.env, "GYM_APP_PASSWORD", None)
        return await wsgi.fetch(app, request, self.env)
