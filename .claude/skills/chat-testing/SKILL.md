---
name: chat-testing
description: How the chat test suite works and how to extend it — pytest, the in-file FakeRedis fake, fixtures, and current coverage gaps. Use when writing, running, or debugging tests.
---

# Chat — Testing

- Runner: **pytest**. Location: `tests/test_chat_api.py`. Run: `pytest tests/ -q`.
- Tests target **`ChatAPI` directly** using a hand-rolled **`FakeRedis`** defined
  in the test file — no real Redis process needed.
- Fixtures: `redis` (a fresh `FakeRedis`) and `chat_api` (wraps it). Tests live
  in `class TestChatAPI`.

## FakeRedis — what it covers, and doesn't

Implemented ops: `sadd`, `smembers`, `sismember`, `srem`, `zadd(nx=)`, `zrange`
(plus `flushdb`). That covers rooms and messages.

> ⚠️ **`FakeRedis` is missing the hash ops** (`hexists`, `hset`, `hget`) that
> `ChatAPI`'s auth (`register_user` / `login_user` / `verify_token`) relies on.
> So once the Pydantic import blocker is cleared, the register/login tests will
> fail with `AttributeError` until `FakeRedis` gains hash support — or you swap
> in the [`fakeredis`](https://pypi.org/project/fakeredis/) library, which
> implements the full command set.

**Rule:** if you call a new Redis method in `api.py`, either extend `FakeRedis`
or migrate the suite to the `fakeredis` library.

## Current state & gaps

- ⚠️ Suite is RED until the Pydantic v1→v2 fix in `models.py` (collection error).
  See [CLAUDE.md](../../../CLAUDE.md).
- Only `ChatAPI` is covered. **No tests** for `routes.py` (Flask), `socket.py`
  (SocketIO), or the client. Adding a Flask `test_client` layer and socket tests
  is a good task for the "improve" phase.
