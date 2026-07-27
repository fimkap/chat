---
name: chat-architecture
description: Architecture of the chat server — component responsibilities, the Redis key schema, and the REST/WebSocket request flows. Use when you need to understand how the app works, where state lives, or before modifying core components. Triggers on "how does X work", "architecture", "data model", "redis keys", "request flow", "where is X stored".
---

# Chat — Architecture

## Components

| File | Responsibility |
|------|----------------|
| `app.py` | Entrypoint. Builds Flask app, registers the REST blueprint, wires SocketIO events, calls `init_rooms()`. |
| `chat/api.py` | **`ChatAPI`** — all business logic and the only place that touches Redis. Auth, rooms, messages. |
| `chat/routes.py` | Flask REST blueprint. Creates the module-level `Redis(host=REDIS_HOST, port=REDIS_PORT)` and the shared `ChatAPI` singleton `chat_api`. |
| `chat/socket.py` | SocketIO handlers: connect/join/message/leave/disconnect. Reuses the same `chat_api`. Holds in-memory `user_sessions` ({sid → {username, room}}) and `authenticated_users` ({sid → {username, token}}). |
| `chat/models.py` | Pydantic models: `User` (name), `Message` (sender_id, timestamp, message), `ChatRoom` (id, topic). |
| `chat/errors.py` | `ChatAPIError(message, status_code, original_exception)`. |
| `chat/config.py` | Env-derived settings: Redis host/port, log dir/level, secret key, host/port, debug. |
| `chat/logger.py` | Logging → stderr + `$CHAT_LOG_DIR/app.log` (default `logs/`). |
| `client/chat_client.py` | CLI Socket.IO client (username → choose room → chat). |

## Redis key schema (reverse-engineered from `api.py`)

| Key | Type | Contents |
|-----|------|----------|
| `users` | hash | `username → argon2id hash` (legacy sha256 hex upgraded on next login) |
| `token:<uuid4>` | string | `username`, with a TTL of `CHAT_TOKEN_TTL` |
| `ratelimit:<scope>:<id>` | string | attempt counter, expires after `CHAT_LOGIN_RATE_WINDOW` |
| `rooms` | set | JSON blobs `{"id": …, "topic": …}` |
| `rooms_ids` | set | room ids (existence checks) |
| `room:<id>:users` | set | usernames currently in the room |
| `room:<id>` | zset | member = message JSON, score = timestamp |

Tokens are **one key each** (not a `tokens` hash) so Redis expires them itself.
A stale `tokens` hash may linger in an old dev database; it is no longer read.
Rate-limit scopes are `login`, `login-ip`, `register-ip`.

## Flows

**REST** (`routes.py`): `POST /register`, `POST /login` → `{token, expires_in}`,
`POST /logout` (revoke), `GET /rooms`, `POST /rooms/<id>/users/me` (join,
`/users/<user>` kept as a legacy alias), `POST /rooms/<id>/messages` (send),
`GET /rooms/<id>/messages`.

Auth is `Authorization: Bearer <token>` via the `require_auth` decorator, which
puts the verified name in `g.username`. **Everything except register/login
requires a token**, and the acting identity always comes *from* the token — the
body's `sender_id` and the path's `<user_id>` are only cross-checked for
backwards compatibility and 401 on mismatch. A `before_request` hook rejects
plaintext with 403 when `CHAT_REQUIRE_HTTPS` is set.

**WebSocket** (`socket.py`): auth happens at the handshake — `handle_connect`
reads `auth={"token": …}` and returns `False` to refuse the connection outright.
The verified name and token are cached per-sid in `authenticated_users`, and
`current_username()` **re-verifies the token on every event**, so expiry or
revocation kills an already-open socket. Clients emit `join` / `message` /
`leave`; the server `send`s room broadcasts and emits `batch` (history on join)
or `error`. Client-supplied usernames in event payloads are ignored.

## Notes before changing things

- Two write paths call `chat_api.send_message`: the REST route and the socket
  handler. Keep their behavior consistent — both now derive the sender from the
  caller's token, so neither trusts a client-supplied name.
- `socket.py` imports `chat_api` from `routes.py`, so importing `socket` (or
  `routes`) triggers creation of the Redis client at import time.
- Keep **all** Redis access inside `ChatAPI`; routes/socket should not touch
  Redis directly. Rate limiting lives in `ChatAPI` for this reason rather than
  in a Flask extension.
- `api.py` reads settings as `config.X` (not `from .config import X`) so tests
  can monkeypatch TTLs and limits. Keep that pattern when adding knobs.
- Verifying a token is a Redis round-trip, and sliding expiry adds a write.
  Socket events re-verify on every message; that is deliberate (revocation must
  take effect mid-session) but it is the hot path if throughput ever matters.
