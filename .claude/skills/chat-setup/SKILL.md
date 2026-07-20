---
name: chat-setup
description: Set up a local dev environment for the chat server — virtualenv, dependencies, running the tests and the app. Use when getting started, installing dependencies, or preparing to develop or contribute.
disable-model-invocation: true
---

# Chat — Local Setup

Verified on Python 3.12 (Dockerfile targets 3.11; 3.10+ is fine).

## 1. Virtualenv + dependencies

No `uv` config or dev-requirements file exists yet. Plain venv + pip works today:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install pytest            # tests need it; it is NOT in requirements.txt
```

(If you later adopt `uv` — as the ADK project does —
`uv venv && uv pip install -r requirements.txt pytest` is the faster equivalent.)

Recommended one-time cleanup: there is **no `.gitignore`**. Add one ignoring
`.venv/`, `__pycache__/`, `logs/`, and `redis-data/` before committing.

## 2. Run the tests

```bash
pytest tests/ -q
```

> ⚠️ **Currently RED.** Collection fails with
> `TypeError: constr() got an unexpected keyword argument 'regex'` — `models.py`
> is Pydantic v1 code on a v2 pin (see [CLAUDE.md](../../../CLAUDE.md) "Known
> state"). This is the first thing to fix. Unit tests use an in-file `FakeRedis`,
> so they need **no** running Redis — see the `chat-testing` skill.

## 3. Run the app

Full stack (server + Redis + nginx) is the reliable path:

```bash
docker-compose up --build     # web on :5002, nginx on :80
```

Running `python app.py` directly **fails outside Docker today**: `logger.py`
opens `/logs/app.log` and `routes.py` connects to host `redis`. See the
`chat-debug` skill for local workarounds.
