# CLAUDE.md — Chat Server

Guidance for Claude Code when working in this repository.

## What this is

A small real-time chat service: a **Flask + Flask-SocketIO** server backed by
**Redis**, plus a **CLI Socket.IO client**. Originally built as a 5-milestone
exercise (REST API → CLI client → Redis persistence → chat rooms → WebSocket
push) — see [README.md](README.md) for the spec. Data models use **Pydantic**.

## Layout

- `app.py` — entrypoint; builds the Flask app, registers the REST blueprint,
  wires SocketIO events, seeds rooms via `init_rooms()`.
- `chat/` — the package:
  - `api.py` — **`ChatAPI`**: all business logic and the *only* place that
    touches Redis (auth, rooms, messages). The heart of the app.
  - `routes.py` — Flask REST blueprint; creates the module-level
    `Redis(host="redis")` and the shared `ChatAPI` singleton `chat_api`.
  - `socket.py` — SocketIO handlers (connect/join/message/leave/disconnect);
    in-memory `user_sessions: {sid -> {username, room}}`.
  - `models.py` — Pydantic models: `User`, `Message`, `ChatRoom`.
  - `errors.py` — `ChatAPIError` (carries an HTTP status code).
  - `config.py` — env-derived settings (Redis host/port, log dir/level, host/port).
  - `logger.py` — logging config (stderr + `$CHAT_LOG_DIR/app.log`).
- `client/chat_client.py` — CLI Socket.IO client.
- `tests/test_chat_api.py` — pytest suite against `ChatAPI` using an in-file `FakeRedis`.
- `Dockerfile`, `docker-compose.yml` (web + redis + nginx), `nginx.conf`,
  `requirements.txt` / `requirements-dev.txt`, `pyproject.toml` (ruff + pytest config).

Full component + Redis data-model map: **`chat-architecture` skill**.

## Common commands

Details in the `chat-setup` and `chat-debug` skills. Quick reference:

```bash
python3 -m venv .venv && . .venv/bin/activate   # create env (or: uv venv .venv)
pip install -r requirements-dev.txt              # runtime + pytest/ruff + client deps
pytest -q                                        # run tests
ruff check .                                     # lint
docker compose up --build                        # full stack: web:5002, redis, nginx:80

# Local run (no Docker) — needs a reachable Redis:
REDIS_HOST=localhost CHAT_PORT=5002 python app.py
```

## Skills (`.claude/skills/`)

- **chat-setup** — create the dev env, install deps, run tests/app.
- **chat-architecture** — components, Redis key schema, REST/WebSocket flows.
- **chat-debug** — run the stack, curl the REST API, drive the socket client, inspect Redis/logs.
- **chat-testing** — how the suite + `FakeRedis` work and how to extend them.
- **chat-style** — coding conventions and the inconsistencies to converge.
- **chat-git** — commit/branch/PR conventions for this repo.
- **chat-modernize** — the dependency-upgrade + cleanup playbook (the planned first project).

## Known state & backlog

**The repo runs.** Modernization pass 1 (2026-07-25) fixed the Pydantic v1/v2
mismatch, bumped every pin to current, and made the app launchable both in
compose and locally. Verified: `pytest` green, `ruff check` clean, REST +
WebSocket exercised through `:5002` and through nginx `:80`.

Configuration is env-driven via `chat/config.py`: `REDIS_HOST`/`REDIS_PORT`,
`CHAT_LOG_DIR` (empty → stderr only), `CHAT_LOG_LEVEL`, `CHAT_SECRET_KEY`,
`CHAT_HOST`/`CHAT_PORT`, `CHAT_DEBUG`; the CLI client reads `CHAT_SERVER_URL`.

**Async mode is now `threading` + `simple-websocket`** (no eventlet/gevent
monkey-patching); gunicorn runs the `gthread` worker with one worker process.
Socket.IO needs a message queue before scaling past `-w 1`.

Remaining backlog:

- **Style convergence** (see `chat-style`): `%` formatting → f-strings, eager →
  lazy logging args, complete type hints. `pyproject.toml` notes the ruff rule
  sets (`UP`, `B`, `G`) to enable when that lands.
- **Test coverage.** Only `ChatAPI` is unit-tested; no Flask `test_client` or
  socket tests. `pytest.raises(Exception)` in three tests should assert
  `ChatAPIError`.
- **Auth is weak by design.** SHA-256 without a salt, UUID tokens with no
  expiry, no auth on the socket handlers.
- **No CI.** Nothing runs `pytest`/`ruff` on push.
- `chat/api.py` still carries a `try: from redis import RedisError` shim for
  environments without the redis package.

## Conventions

- Errors: raise `ChatAPIError(msg, status_code)` inside `ChatAPI`; routes catch
  it and map to a JSON body + status code.
- **All Redis access stays inside `ChatAPI`** — routes and socket handlers must
  not touch Redis directly.
- Unit tests target `ChatAPI` with an in-memory `FakeRedis`; no live Redis.
