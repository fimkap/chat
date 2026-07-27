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

## Exercise the REST API

```bash
BASE=http://localhost:5002
curl -sX POST $BASE/register -H 'Content-Type: application/json' \
  -d '{"username":"alice","password":"pw"}'
TOKEN=$(curl -sX POST $BASE/login -H 'Content-Type: application/json' \
  -d '{"username":"alice","password":"pw"}' \
  | python -c 'import sys,json;print(json.load(sys.stdin)["token"])')
curl -s $BASE/rooms
curl -sX POST $BASE/rooms/1/users/alice -H "Authorization: Bearer $TOKEN"
curl -sX POST $BASE/rooms/1/messages -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"sender_id":"alice","message":"hi"}'
curl -s $BASE/rooms/1/messages
```

## Drive the socket client

```bash
python client/chat_client.py                       # prompts for username + room
CHAT_SERVER_URL=http://localhost python client/chat_client.py   # via nginx
```

Client deps are in `requirements-client.txt` (not `requirements.txt`). Ctrl-C /
Ctrl-D — or piped stdin running out — disconnects and exits cleanly.

## Logs & Redis

- Logs: stderr (`docker compose logs -f web`) plus `./logs/app.log` (mounted
  volume; `/logs/app.log` inside the container).
- Inspect Redis: `docker compose exec redis redis-cli` → then e.g.
  `KEYS *`, `HGETALL users`, `SMEMBERS rooms`, `ZRANGE room:1 0 -1`.
