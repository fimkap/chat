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
| `chat/routes.py` | Flask REST blueprint. Creates the module-level `Redis(host="redis")` and the shared `ChatAPI` singleton `chat_api`. |
| `chat/socket.py` | SocketIO handlers: connect/join/message/leave/disconnect. Reuses the same `chat_api`. Holds in-memory `user_sessions` ({sid → {username, room}}). |
| `chat/models.py` | Pydantic models: `User` (name), `Message` (sender_id, timestamp, message), `ChatRoom` (id, topic). |
| `chat/errors.py` | `ChatAPIError(message, status_code, original_exception)`. |
| `chat/logger.py` | Logging → `/logs/app.log`. |
| `client/chat_client.py` | CLI Socket.IO client (username → choose room → chat). |

## Redis key schema (reverse-engineered from `api.py`)

| Key | Type | Contents |
|-----|------|----------|
| `users` | hash | `username → sha256(password)` |
| `tokens` | hash | `token (uuid4) → username` |
| `rooms` | set | JSON blobs `{"id": …, "topic": …}` |
| `rooms_ids` | set | room ids (existence checks) |
| `room:<id>:users` | set | usernames currently in the room |
| `room:<id>` | zset | member = message JSON, score = timestamp |

## Flows

**REST** (`routes.py`): `POST /register`, `POST /login` → token, `GET /rooms`,
`POST /rooms/<id>/users/<user>` (join), `POST /rooms/<id>/messages` (send),
`GET /rooms/<id>/messages`. Auth is `Authorization: Bearer <token>`; the token's
username must match the acting user/sender or the route returns 401.

**WebSocket** (`socket.py`): client emits `join` / `message` / `leave`; server
`send`s room broadcasts and emits `batch` (message history on join) or `error`.
A message is persisted via `chat_api.send_message`, then broadcast to the room.

## Notes before changing things

- Two write paths call `chat_api.send_message`: the REST route and the socket
  handler. Keep their behavior consistent.
- `socket.py` imports `chat_api` from `routes.py`, so importing `socket` (or
  `routes`) triggers creation of the Redis client at import time.
- Keep **all** Redis access inside `ChatAPI`; routes/socket should not touch
  Redis directly.
