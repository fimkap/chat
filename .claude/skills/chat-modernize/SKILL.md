---
name: chat-modernize
description: Playbook for upgrading the chat project's dependencies to current versions and modernizing the code — order of operations, per-library migration gotchas, and the verify loop. Use when bumping dependencies, fixing deprecations, or planning the modernization work.
---

# Chat — Modernization Playbook

The stated goal for this repo: bring dependencies to current versions, then
improve the code. This skill is the map.

## Status — pass 1 done (2026-07-25)

Dependencies and launchability are **done**; the "improve the code" phase is not.

- Pydantic v2 idioms fixed (`pattern=`, `.model_dump()`); suite green after
  adding hash ops (`hset`/`hget`/`hexists`/`hdel`) to `FakeRedis`.
- Pins now: redis 8.0.1, pydantic 2.13.4, Flask 3.1.3, Flask-SocketIO 5.6.1,
  python-socketio 5.16.3, simple-websocket 1.1.0, gunicorn 26.0.0.
  `requirements-dev.txt` adds pytest 9.1.1 + ruff 0.16.0 + client deps.
- **eventlet is gone.** `async_mode="threading"` + `simple-websocket`, served by
  gunicorn `--worker-class gthread --threads 100 -w 1`. Docker base image is
  `python:3.13-slim`.
- Config is env-driven (`chat/config.py`); `logger.py` logs to stderr plus
  `$CHAT_LOG_DIR/app.log`; nginx proxies `web:5002` with WebSocket upgrade;
  compose waits on a redis healthcheck.
- `pyproject.toml` added with ruff (`E4,E7,E9,F,I`) + pytest config.

**Verified:** `pytest -q` (7 passed), `ruff check .` clean, and REST + WebSocket
smoke tests (two clients, join/message/leave, transport == `websocket`) against
`:5002`, through nginx `:80`, and against a local `python app.py` run.

Still open: style convergence (`UP`/`B`/`G` rules — % formatting, lazy logging,
type hints), Flask `test_client` + socket tests, real auth hardening, CI.

The rest of this file is the original plan, kept for the per-library notes.

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
