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
  **Half-done:** `CHAT_CORS_ORIGINS` exists in `chat/config.py` and is wired to
  `SocketIO(cors_allowed_origins=...)` in `app.py` (unset → the library's
  same-origin default). The **REST blueprint still has no CORS** — add
  `flask-cors` driven by that same config value when the UI lands on a separate
  origin. Never hard-code origins.
- **Socket auth handshake.** Auth is enforced at connect time: the client must
  pass `auth={"token": <token>}` and the server rejects tokenless connections
  (`chat/socket.py`, `handle_connect`). The JS client does this via
  `io(url, { auth: { token } })`. Preserve this contract; the UI depends on it.
- **Tokens expire — the UI must handle 401 everywhere.** `POST /login` returns
  `{"token": ..., "expires_in": <seconds>}` (default 3600). Expiry is *sliding*
  by default (`CHAT_TOKEN_SLIDING_EXPIRY`), so an active session stays alive and
  an idle one lapses. The UI needs to:
  - treat `401` on any call as "session over" → clear the token, show login;
  - handle a **mid-session socket drop**: the server re-verifies the token on
    every event, so an expired or revoked session gets an `error` event and an
    immediate disconnect. Don't blindly auto-reconnect with the dead token —
    Socket.IO's default reconnect loop will hammer the server (visible as
    repeated "Rejected unauthenticated socket connection" warnings).
- **Logout exists:** `POST /logout` revokes the token server-side. Wire it to
  the UI's logout button; don't just drop the token client-side.
- **Rate limiting returns 429.** Login/register are limited (per username and
  per IP). Surface a real "too many attempts, wait a minute" message rather than
  a generic failure. Note the per-IP budget is shared by everyone behind the
  proxy, so don't add retry-on-failure loops to the login form.
- **Identity comes from the token — do not send usernames.** Both REST and the
  socket now derive the acting user from the token. `POST /rooms/<id>/messages`
  takes just `{"message": ...}`; joining is `POST /rooms/<id>/users/me`. Sending
  a `sender_id`/`<user_id>` that isn't the token owner returns 401. The UI should
  never transmit the current username as an identity claim.
- **Error shape.** REST errors are `{"error": <str>}` + status code; socket
  errors are `emit("error", {"data": <str>})`. The UI has to parse both — keep
  them consistent and don't leak internal detail in messages.
- **Static serving vs. separate app.** Decide when the UI is built: Flask serves
  the built assets (same origin → no CORS) OR a separate dev server (different
  origin → CORS required). Prefer same-origin serving to sidestep CORS if the UI
  is a simple SPA; note the choice here when made.
- **HTTPS in production.** Bearer tokens in headers are only safe over TLS. Run
  the TLS overlay (`docker-compose.tls.yml` + `scripts/gen-dev-certs.sh`) and set
  `CHAT_REQUIRE_HTTPS=1`. Browser storage of tokens plus plaintext transport is
  the worst combination — don't ship the UI without this.
- **Token storage in the browser.** `localStorage` persists across tabs but is
  readable by any XSS; in-memory is safest but drops on refresh. Given tokens now
  expire and can be revoked, in-memory (or `sessionStorage`) plus a re-login
  prompt is the recommended default. Decide explicitly and record it here.
- **Remaining auth weaknesses** (see CLAUDE.md backlog): tokens are opaque
  random strings with no refresh-token flow, and there is no per-user "revoke all
  sessions". Password hashing, expiry, revocation, rate limiting, and transport
  are now handled.

## Related

- `chat-architecture` — REST/WebSocket flows and the Redis schema the UI reads.
- `chat-style` — conventions any new frontend-facing server code must follow.
- `chat-testing` — the UI will need Flask `test_client` coverage for the REST
  routes it depends on (currently only `ChatAPI` is unit-tested).
