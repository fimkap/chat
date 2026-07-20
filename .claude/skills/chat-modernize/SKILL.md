---
name: chat-modernize
description: Playbook for upgrading the chat project's dependencies to current versions and modernizing the code — order of operations, per-library migration gotchas, and the verify loop. Use when bumping dependencies, fixing deprecations, or planning the modernization work.
---

# Chat — Modernization Playbook

The stated goal for this repo: bring dependencies to current versions, then
improve the code. This skill is the map. **Nothing here is done yet** — it's the
plan.

## Order of operations

1. **Get to green FIRST.** The suite can't validate upgrades while it's red.
   The blocker is Pydantic v1 code on a v2 pin — fix that before touching versions:
   - `chat/models.py`: `constr(regex=...)` → `constr(pattern=...)` (verified: the
     rename is all that's needed on the pinned 2.1.1).
   - `chat/models.py`, `chat/routes.py`, `chat/api.py`: `.dict()` → `.model_dump()`.
   - Run `pytest tests/ -q`. Next expected failure: the auth tests, because
     `FakeRedis` lacks hash ops — see the `chat-testing` skill.
2. **Upgrade one library (or one cohesive group) at a time.** After each bump:
   `pytest tests/ -q` + a smoke test (`chat-debug` skill). Commit per step so a
   regression is easy to bisect.
3. **Regenerate pins.** Produce a fresh `requirements.txt` and split out a
   `requirements-dev.txt` (pytest, ruff, mypy). Consider `uv` or `pip-tools` to
   manage them.

## Per-library migration notes

Current pins → recent (early-2026) targets. **Verify the latest on PyPI** — these
drift.

| Package | Pinned | Target | Watch for |
|---------|--------|--------|-----------|
| pydantic | 2.1.1 | 2.11.x | `regex`→`pattern`, `.dict()`→`.model_dump()`, `@validator`→`@field_validator`. (Only the first two appear in this code.) |
| Flask | 2.3.2 | 3.1.x | Flask 3 requires Werkzeug 3 — pin them together. (The current install already pulled Werkzeug 3.1.8 against Flask 2.3, which is itself an unpinned mismatch.) |
| redis | 3.5.3 | 5.2.x | Big jump. redis-py 4 merged async + changed some kwargs; `zadd(mapping=...)` (already used) is fine. Re-check `hset`/`hget` decode behavior and connection/SSL args. |
| Flask-SocketIO | 5.3.5 | 5.5.x | Track with `python-socketio`; re-check the `async_mode` choice below. |
| eventlet | 0.33.3 | 0.40.x | ⚠️ eventlet monkey-patching is fragile on Python 3.12+. Strongly consider switching `async_mode` to `gevent` or `threading`, or moving to an ASGI stack. Test the socket path explicitly. |
| gunicorn | 21.2.0 | 23.x | Minor; re-verify the `--worker-class eventlet` line if you change async_mode. |

## While you're in there (quick wins, optional)

These are the non-dependency items from CLAUDE.md's backlog:

- **nginx port mismatch:** `nginx.conf` → `web:5000` but the server binds `:5002`.
- **Hardcoded infra:** `logger.py` (`/logs/app.log`) and `routes.py`
  (`Redis(host="redis")`) should read from env vars / config so the app runs
  locally and in Docker.
- **Test coverage:** add Flask `test_client` and socket tests (currently only
  `ChatAPI` is exercised).

## Verify loop

After each change: `pytest tests/ -q`, then `docker-compose up --build` and run
through the `chat-debug` curl + socket-client checks. Green tests alone don't
prove the socket path — exercise it.
