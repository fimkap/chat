---
name: chat-frontend
description: Planned web frontend UI for the chat server and the design constraints it puts on every change. The UI will drive the app over the REST API + WebSocket, so keep those interfaces browser-usable. Use when planning or making ANY change to routes, auth, sockets, config, or the data model — check it will not break the future UI. Triggers on "frontend", "UI", "web client", "browser", "CORS", "REST API design", "should I remove this route".
---

# Chat — Frontend UI (planned)

**Status: planned, not built yet.** A web frontend UI is on the roadmap. It will
be a browser app (its own origin) that drives the chat over the **REST API** for
request/response actions and the **WebSocket** for real-time push. Treat both
interfaces as first-class public contracts, not internal glue.

Consult this skill before any change to `routes.py`, `socket.py`, `api.py`,
`config.py`, or the models — and confirm the change keeps the future UI viable.

## Consequences for current work

- **The REST messaging routes are NOT dead — do not retire them.** `POST
  /rooms/<id>/users/<id>` (join), `POST /rooms/<id>/messages` (send), and `GET
  /rooms/<id>/messages` are unused by the CLI client (which uses the socket) but
  will be the UI's primary REST surface. Keep them working and tested. If asked
  to "remove the unused routes," push back — they are future UI endpoints.
- **REST is the design target; the CLI is legacy.** When REST and socket
  behavior diverge, converge toward what a browser UI needs.

## Design checklist (apply to every relevant change)

- **CORS.** A browser UI on a different origin cannot call the API without it.
  Not configured yet. When the UI lands (or is being prepared for), add
  `flask-cors` for the REST blueprint and set `cors_allowed_origins` on
  `SocketIO(...)`. Drive the allowed origin(s) from `chat/config.py` (env var),
  never hard-code. Don't add CORS speculatively, but never make a change that
  makes adding it harder.
- **Socket auth handshake.** Auth is now enforced at connect time: the client
  must pass `auth={"token": <token>}` and the server rejects tokenless
  connections (see `chat/socket.py`, `handle_connect`). The JS Socket.IO client
  does this via `io(url, { auth: { token } })`. Preserve this contract; the UI
  depends on it.
- **Token handling must stay browser-friendly.** Login returns a bearer token
  the UI keeps in memory / storage and sends as `Authorization: Bearer <token>`
  (REST) and in the socket `auth` (WebSocket). Keep tokens JSON-serializable and
  the login response shape stable (`{"token": ...}`).
- **Identity consistency (known divergence to converge).** REST routes require
  the caller to pass `sender_id`/`user_id` and check it matches the token; the
  socket now *derives* identity from the token and ignores client-supplied
  usernames. The UI is simpler if both derive identity from the token — prefer
  moving REST toward token-derived identity rather than widening the gap.
- **Error shape.** REST errors are `{"error": <str>}` + status code; socket
  errors are `emit("error", {"data": <str>})`. The UI has to parse both — keep
  them consistent and don't leak internal detail in messages.
- **Static serving vs. separate app.** Decide when the UI is built: Flask serves
  the built assets (same origin → no CORS) OR a separate dev server (different
  origin → CORS required). Prefer same-origin serving to sidestep CORS if the UI
  is a simple SPA; note the choice here when made.
- **Auth is weak by design** (SHA-256 no salt, non-expiring UUID tokens, see
  CLAUDE.md backlog). A public browser UI raises the stakes — flag this when
  touching auth; don't quietly ship the UI on top of it without calling it out.

## Related

- `chat-architecture` — REST/WebSocket flows and the Redis schema the UI reads.
- `chat-style` — conventions any new frontend-facing server code must follow.
- `chat-testing` — the UI will need Flask `test_client` coverage for the REST
  routes it depends on (currently only `ChatAPI` is unit-tested).
