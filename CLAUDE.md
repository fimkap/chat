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
    in-memory `user_sessions: {sid -> {username, room}}` and
    `authenticated_users: {sid -> {username, token}}`.
  - `models.py` — Pydantic models: `User`, `Message`, `ChatRoom`.
  - `errors.py` — `ChatAPIError` (carries an HTTP status code).
  - `config.py` — env-derived settings (Redis, logging, host/port, auth knobs).
  - `logger.py` — logging config (stderr + `$CHAT_LOG_DIR/app.log`).
- `client/chat_client.py` — CLI Socket.IO client (logs in, then connects).
- `tests/` — `conftest.py` (shared `FakeRedis` + fixtures),
  `test_chat_api.py` (`ChatAPI` units), `test_routes.py` (Flask `test_client`).
- `Dockerfile`, `docker-compose.yml` (web + redis + nginx), `nginx.conf`,
  `docker-compose.tls.yml` + `nginx.tls.conf` + `scripts/gen-dev-certs.sh`
  (opt-in HTTPS), `requirements.txt` / `requirements-dev.txt`,
  `pyproject.toml` (ruff + pytest config).

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
- **chat-frontend** — the planned web UI and the design constraints it imposes
  (keep REST routes browser-usable, CORS, socket auth handshake, token handling).

## Known state & backlog

**The repo runs.** Modernization pass 1 (2026-07-25) fixed the Pydantic v1/v2
mismatch, bumped every pin to current, and made the app launchable both in
compose and locally. Verified: `pytest` green, `ruff check` clean, REST +
WebSocket exercised through `:5002` and through nginx `:80`.

Auth hardening pass (2026-07-27) closed the gap where the socket handlers
trusted a client-supplied username. Now: **argon2id** password hashing (legacy
sha256 digests upgrade transparently on next login), tokens stored as
`token:<uuid>` keys with a TTL and sliding expiry, `POST /logout` revocation,
Redis-counter rate limiting on login/register, token-derived identity on **both**
REST and socket, per-event socket re-verification, and an opt-in TLS stack.
Verified: 56 pytest tests green, `ruff check`/`ruff format` clean, and a 23-check
end-to-end smoke test passing over `:5002`, nginx `:80`, and HTTPS `:443`.

Configuration is env-driven via `chat/config.py`: `REDIS_HOST`/`REDIS_PORT`,
`CHAT_LOG_DIR` (empty → stderr only), `CHAT_LOG_LEVEL`, `CHAT_SECRET_KEY`,
`CHAT_HOST`/`CHAT_PORT`, `CHAT_DEBUG`, plus auth knobs `CHAT_TOKEN_TTL`,
`CHAT_TOKEN_SLIDING_EXPIRY`, `CHAT_LOGIN_RATE_LIMIT`,
`CHAT_LOGIN_RATE_LIMIT_PER_IP`, `CHAT_REGISTER_RATE_LIMIT_PER_IP`,
`CHAT_LOGIN_RATE_WINDOW`, `CHAT_REQUIRE_HTTPS`, `CHAT_CORS_ORIGINS`; the CLI
client reads `CHAT_SERVER_URL`.

HTTPS is opt-in and off by default so `docker compose up` needs no certs:
`./scripts/gen-dev-certs.sh` then
`docker compose -f docker-compose.yml -f docker-compose.tls.yml up --build`.

**Async mode is now `threading` + `simple-websocket`** (no eventlet/gevent
monkey-patching); gunicorn runs the `gthread` worker with one worker process.
Socket.IO needs a message queue before scaling past `-w 1`.

Remaining backlog:

- **Style convergence** (see `chat-style`): `%` formatting → f-strings, eager →
  lazy logging args, complete type hints. `pyproject.toml` notes the ruff rule
  sets (`UP`, `B`, `G`) to enable when that lands.
- **Test coverage.** `ChatAPI` and the REST routes are covered (56 tests, incl.
  Flask `test_client`). **No socket tests** — `socket.py` is only exercised
  manually; `socketio.test_client(app)` would close that gap.
- **Auth leftovers.** Tokens are opaque with no refresh-token flow and there is
  no per-user "revoke all sessions". Rate-limit counters are fixed-window (a
  burst can straddle the boundary). `certs/` is gitignored — production needs
  real certificates, not `scripts/gen-dev-certs.sh`.
- **REST CORS is not configured.** `CHAT_CORS_ORIGINS` is wired to Socket.IO
  only; the REST blueprint needs `flask-cors` before a cross-origin browser UI
  works. See the `chat-frontend` skill.
- **Planned web UI** (see `chat-frontend`). Will drive the app over the REST API
  + WebSocket, so keep REST routes browser-usable and don't retire the REST
  messaging routes (still unused by the CLI client, which chats over the socket).
  The UI must handle token expiry, `401` mid-session, and `429` on login.
- **No CI.** Nothing runs `pytest`/`ruff` on push.
- `chat/api.py` still carries a `try: from redis import RedisError` shim for
  environments without the redis package.

## Conventions

- Errors: raise `ChatAPIError(msg, status_code)` inside `ChatAPI`; routes catch
  it and map to a JSON body + status code.
- **All Redis access stays inside `ChatAPI`** — routes and socket handlers must
  not touch Redis directly.
- **Never trust a client-supplied identity.** Derive the acting user from the
  auth token: `g.username` (set by `require_auth` in routes) or
  `current_username()` (socket). A `sender_id`/`user_id` in a payload may only be
  cross-checked against the token, never used as the identity.
- Auth-relevant settings are read as `config.X` at call time (not imported by
  value) so tests can monkeypatch them.
- Tests target `ChatAPI` and the routes with an in-memory `FakeRedis`; no live
  Redis. Extend `FakeRedis` in `tests/conftest.py` when using a new Redis command.
