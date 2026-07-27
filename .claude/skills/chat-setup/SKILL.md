---
name: chat-setup
description: Set up a local dev environment for the chat server — virtualenv, dependencies, running the tests and the app. Use when getting started, installing dependencies, or preparing to develop or contribute.
disable-model-invocation: true
---

# Chat — Local Setup

Verified on Python 3.12 (Dockerfile targets 3.13; 3.10+ is fine).

## 1. Virtualenv + dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt   # runtime + pytest/ruff + CLI-client deps
```

`requirements.txt` alone is runtime-only (what the Docker image installs).

`uv` is the faster equivalent and doesn't need the `python3-venv` system package:

```bash
uv venv .venv && VIRTUAL_ENV=.venv uv pip install -r requirements-dev.txt
```

## 2. Run the tests

```bash
pytest -q          # testpaths=tests is set in pyproject.toml
ruff check .
```

Both are green. Unit tests use an in-file `FakeRedis`, so they need **no**
running Redis — see the `chat-testing` skill.

## 3. Run the app

Full stack (server + Redis + nginx):

```bash
docker compose up --build     # web on :5002, nginx on :80
```

Locally, all you need is a reachable Redis — everything else is env-configurable
(`chat/config.py`):

```bash
docker run --rm -d -p 6379:6379 redis
REDIS_HOST=localhost python app.py    # :5002, logs to ./logs/app.log + stderr
```
