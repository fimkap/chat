---
name: chat-testing
description: How the chat test suite works and how to extend it — pytest, the in-file FakeRedis fake, fixtures, and current coverage gaps. Use when writing, running, or debugging tests.
---

# Chat — Testing

- Runner: **pytest**. Location: `tests/test_chat_api.py`. Run: `pytest -q`
  (`testpaths = ["tests"]` lives in `pyproject.toml`).
- Tests target **`ChatAPI` directly** using a hand-rolled **`FakeRedis`** defined
  in the test file — no real Redis process needed.
- Fixtures: `redis` (a fresh `FakeRedis`) and `chat_api` (wraps it). Tests live
  in `class TestChatAPI`.

## FakeRedis — what it covers, and doesn't

Implemented ops: `sadd`, `smembers`, `sismember`, `srem`, `zadd(nx=)`, `zrange`,
`hset`, `hget`, `hexists`, `hdel` (plus `flushdb`). That covers rooms, messages,
and auth. Values are returned as **bytes**, matching redis-py's default decoding.

If you need much more of the command set, swap in the
[`fakeredis`](https://pypi.org/project/fakeredis/) library instead of growing
this fake.

**Rule:** if you call a new Redis method in `api.py`, either extend `FakeRedis`
or migrate the suite to the `fakeredis` library.

## Current state & gaps

- Suite is **green** (7 tests) as of the 2026-07-25 modernization pass.
- Three tests use `pytest.raises(Exception)` — they should assert `ChatAPIError`
  (ruff's `B017` flags this once the `B` rules are enabled).
- Only `ChatAPI` is covered. **No tests** for `routes.py` (Flask), `socket.py`
  (SocketIO), or the client. Adding a Flask `test_client` layer and socket tests
  is a good task for the "improve" phase.
