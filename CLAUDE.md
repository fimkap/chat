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
  - `logger.py` — logging config (writes to `/logs/app.log`).
- `client/chat_client.py` — CLI Socket.IO client.
- `tests/test_chat_api.py` — pytest suite against `ChatAPI` using an in-file `FakeRedis`.
- `Dockerfile`, `docker-compose.yml` (web + redis + nginx), `nginx.conf`, `requirements.txt`.

Full component + Redis data-model map: **`chat-architecture` skill**.

## Common commands

Details in the `chat-setup` and `chat-debug` skills. Quick reference:

```bash
python3 -m venv .venv && . .venv/bin/activate   # create env
pip install -r requirements.txt pytest          # install (pytest is not in requirements)
pytest tests/ -q                                 # run tests
docker-compose up --build                        # full stack: web:5002, redis, nginx:80
```

## Skills (`.claude/skills/`)

- **chat-setup** — create the dev env, install deps, run tests/app.
- **chat-architecture** — components, Redis key schema, REST/WebSocket flows.
- **chat-debug** — run the stack, curl the REST API, drive the socket client, inspect Redis/logs.
- **chat-testing** — how the suite + `FakeRedis` work and how to extend them.
- **chat-style** — coding conventions and the inconsistencies to converge.
- **chat-git** — commit/branch/PR conventions for this repo.
- **chat-modernize** — the dependency-upgrade + cleanup playbook (the planned first project).

## Known state & backlog (as of setup)

> ⚠️ **The repo is not runnable as-is.** Fixing this is item #1.

- **Pydantic v1 code on a v2 pin.** `models.py` uses `constr(regex=...)` and
  `.dict()` (Pydantic v1 idioms), but `requirements.txt` pins `pydantic==2.1.1`.
  Importing `chat.models` raises
  `TypeError: constr() got an unexpected keyword argument 'regex'`, so **the app
  won't start and every test errors at collection.** Fix: `regex=` → `pattern=`,
  `.dict()` → `.model_dump()`.
- **Stale pins.** All dependencies are old (Flask 2.3, redis 3.5, eventlet 0.33,
  Flask-SocketIO 5.3, gunicorn 21). Upgrading to current versions is the planned
  first project; note `redis` 3.5→5.x and Flask/Werkzeug have API/behavior changes.
- **Local-run friction.** `logger.py` writes to `/logs/app.log` (absolute path)
  and `routes.py` hardcodes `Redis(host="redis")` — both assume the compose
  network. Running outside Docker needs a writable `/logs` and a reachable Redis.
- **nginx port mismatch.** `nginx.conf` proxies to `web:5000`, but the server
  binds `:5002`.
- **Missing hygiene.** No `.gitignore`, no dev-requirements, no linter/formatter
  config, no CI.

## Conventions

- Errors: raise `ChatAPIError(msg, status_code)` inside `ChatAPI`; routes catch
  it and map to a JSON body + status code.
- **All Redis access stays inside `ChatAPI`** — routes and socket handlers must
  not touch Redis directly.
- Unit tests target `ChatAPI` with an in-memory `FakeRedis`; no live Redis.
