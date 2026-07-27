---
name: chat-debug
description: Run and debug the chat server — the docker-compose stack, local-run workarounds, curl-ing the REST API, driving the Socket.IO client, reading logs, and inspecting Redis. Use when running the app, reproducing behavior, or troubleshooting.
---

# Chat — Run & Debug

## Full stack

```bash
docker compose up --build
# web (gunicorn gthread + simple-websocket) on :5002, redis, nginx on :80
```

Both entrypoints work: `http://localhost:5002` direct, or `http://localhost`
through nginx (which forwards WebSocket upgrades).

## Run locally (outside Docker)

Only a reachable Redis is required; the rest is env-driven (`chat/config.py`):

```bash
docker run --rm -d -p 6379:6379 redis
REDIS_HOST=localhost python app.py                      # Flask dev server, :5002
# or:
REDIS_HOST=localhost gunicorn --worker-class gthread --threads 100 -w 1 \
  --bind :5002 app:app
```

Env vars: `REDIS_HOST`, `REDIS_PORT`, `CHAT_LOG_DIR` (empty → stderr only),
`CHAT_LOG_LEVEL`, `CHAT_SECRET_KEY`, `CHAT_HOST`, `CHAT_PORT`, `CHAT_DEBUG`.
Auth knobs: `CHAT_TOKEN_TTL`, `CHAT_TOKEN_SLIDING_EXPIRY`,
`CHAT_LOGIN_RATE_LIMIT`, `CHAT_LOGIN_RATE_LIMIT_PER_IP`,
`CHAT_REGISTER_RATE_LIMIT_PER_IP`, `CHAT_LOGIN_RATE_WINDOW`,
`CHAT_REQUIRE_HTTPS`, `CHAT_CORS_ORIGINS`.

## HTTPS stack

```bash
./scripts/gen-dev-certs.sh          # self-signed certs into ./certs (gitignored)
docker compose -f docker-compose.yml -f docker-compose.tls.yml up --build
curl -k https://localhost/rooms     # -k: the dev cert is self-signed
```

The overlay sets `CHAT_REQUIRE_HTTPS=1`, so hitting the app directly over
plaintext `:5002` then returns `403 {"error": "HTTPS required"}` — that is the
enforcement working, not a bug. The CLI client does not skip cert verification,
so it cannot talk to the self-signed TLS stack; use the plain stack for it.

## Exercise the REST API

**Every route except `/register` and `/login` needs a bearer token**, and the
acting user is always derived from that token.

```bash
BASE=http://localhost:5002
curl -sX POST $BASE/register -H 'Content-Type: application/json' \
  -d '{"username":"alice","password":"pw"}'
TOKEN=$(curl -sX POST $BASE/login -H 'Content-Type: application/json' \
  -d '{"username":"alice","password":"pw"}' \
  | python -c 'import sys,json;print(json.load(sys.stdin)["token"])')
curl -s $BASE/rooms -H "Authorization: Bearer $TOKEN"
curl -sX POST $BASE/rooms/1/users/me -H "Authorization: Bearer $TOKEN"
# No sender_id needed — it comes from the token. Sending someone else's -> 401.
curl -sX POST $BASE/rooms/1/messages -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"message":"hi"}'
curl -s $BASE/rooms/1/messages -H "Authorization: Bearer $TOKEN"
curl -sX POST $BASE/logout -H "Authorization: Bearer $TOKEN"   # revokes it
```

Debugging auth responses: `401` = missing/expired/revoked token, or acting as
another user; `429` = rate limited (5 failed logins per username per minute by
default — wait out `CHAT_LOGIN_RATE_WINDOW` or raise `CHAT_LOGIN_RATE_LIMIT`);
`403 HTTPS required` = `CHAT_REQUIRE_HTTPS` is on and the request arrived
without `X-Forwarded-Proto: https`.

## Drive the socket client

```bash
python client/chat_client.py                       # username + password + room
CHAT_SERVER_URL=http://localhost python client/chat_client.py   # via nginx
```

It prompts for a password, registers the user if new, logs in, and passes the
token in the socket handshake. On exit it calls `/logout` to revoke the token.

Client deps are in `requirements-client.txt` (not `requirements.txt`). Ctrl-C /
Ctrl-D — or piped stdin running out — disconnects and exits cleanly.

**Scripted input needs pacing.** Piping all answers at once
(`printf 'user\npw\n1\nhi\n' | python client/chat_client.py`) races: the client
emits `join` while the transport is still upgrading from polling to WebSocket,
and the immediate EOF disconnects before the message is flushed, so it never
persists. Insert `sleep`s between lines when scripting it.

## Logs & Redis

- Logs: stderr (`docker compose logs -f web`) plus `./logs/app.log` (mounted
  volume; `/logs/app.log` inside the container).
- Inspect Redis: `docker compose exec redis redis-cli` → then e.g.
  `KEYS *`, `HGETALL users`, `SMEMBERS rooms`, `ZRANGE room:1 0 -1`.
- Auth state: `--scan --pattern 'token:*'` lists live sessions, `GET token:<t>`
  gives the owner, `TTL token:<t>` the remaining lifetime. Rate-limit counters
  are `ratelimit:<scope>:<id>` — `DEL` one to unblock yourself while testing.
