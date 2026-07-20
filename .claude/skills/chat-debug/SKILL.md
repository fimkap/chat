---
name: chat-debug
description: Run and debug the chat server — the docker-compose stack, local-run workarounds, curl-ing the REST API, driving the Socket.IO client, reading logs, and inspecting Redis. Use when running the app, reproducing behavior, or troubleshooting.
---

# Chat — Run & Debug

## Full stack

```bash
docker-compose up --build
# web (gunicorn + eventlet) on :5002, redis, nginx on :80
```

> ⚠️ `nginx.conf` proxies to `web:5000` but the server binds `:5002`, so nginx
> routing is currently broken. Hit the server directly on `:5002`.

## Run locally (outside Docker)

Two things assume the compose network:

- `logger.py` → `/logs/app.log`. Create it first:
  `sudo mkdir -p /logs && sudo chown "$USER" /logs` (or edit the path).
- `routes.py` → `Redis(host="redis")`. Start a local Redis
  (`docker run -p 6379:6379 redis`) and point the client at `localhost`.

Then: `python app.py` (Flask dev server) or
`gunicorn --worker-class eventlet -w 1 --bind :5002 app:app`.

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
python client/chat_client.py   # prompts for username + room; talks to localhost:5002
```

## Logs & Redis

- Logs: `./logs/app.log` (mounted volume) or `/logs/app.log` inside the container.
- Inspect Redis: `docker-compose exec redis redis-cli` → then e.g.
  `KEYS *`, `HGETALL users`, `SMEMBERS rooms`, `ZRANGE room:1 0 -1`.
