---
name: chat-testing
description: How the chat test suite works and how to extend it — pytest, the shared FakeRedis fake, fixtures, and current coverage gaps. Use when writing, running, or debugging tests.
---

# Chat — Testing

- Runner: **pytest**. Run: `pytest -q`. Config in `pyproject.toml`
  (`testpaths = ["tests"]`, `pythonpath = ["."]` — no `sys.path` hacks needed).
- Layout:
  - `tests/conftest.py` — **`FakeRedis`** plus shared fixtures.
  - `tests/test_chat_api.py` — unit tests against `ChatAPI`.
  - `tests/test_routes.py` — Flask `test_client` tests for the REST surface.
- No real Redis process is ever needed.

## Fixtures

- `redis` — a fresh `FakeRedis`. Call `redis.seed_rooms()` for the three default
  rooms, and `redis.advance(seconds)` to move its **fake clock** so TTLs lapse
  without sleeping.
- `chat_api` (in `test_chat_api.py`) — a `ChatAPI` wrapping that fake.
- `client` (in `test_routes.py`) — builds a `Flask` app, registers `routes.bp`,
  and monkeypatches `routes.chat_api.redis` to the fake. Because `socket.py`
  shares that same `chat_api` object, the swap covers both.
- `fast_password_hashing` — session-scoped, **autouse**. Swaps
  `api._password_hasher` for cheap argon2 parameters so hashing does not dominate
  runtime (the full suite runs in well under a second). Production keeps the
  library defaults.

## Testing config-driven behavior

`api.py`/`routes.py` read settings as `config.X` at call time, so
monkeypatch the module attribute, not an import:

```python
def test_something(chat_api, monkeypatch):
    monkeypatch.setattr(config, "TOKEN_TTL", 60)
```

Knobs worth exercising: `TOKEN_TTL`, `TOKEN_SLIDING_EXPIRY`, `LOGIN_RATE_LIMIT`,
`LOGIN_RATE_LIMIT_PER_IP`, `REGISTER_RATE_LIMIT_PER_IP`, `LOGIN_RATE_WINDOW`,
`REQUIRE_HTTPS`.

## FakeRedis — what it covers, and doesn't

Implemented: `set(ex=)`, `get`, `incr`, `delete`, `expire`, `ttl`, `sadd`,
`smembers`, `sismember`, `srem`, `zadd(nx=)`, `zrange`, `hset`, `hget`,
`hexists`, `hdel`, plus `flushdb`/`advance`/`seed_rooms`. Values come back as
**bytes**, matching redis-py's default decoding. Expiry is modelled against
`redis.clock` and applied lazily on read.

**Rule:** if you call a new Redis method in `api.py`, either extend `FakeRedis`
or migrate the suite to the [`fakeredis`](https://pypi.org/project/fakeredis/)
library. Don't let production code drift ahead of the fake.

## Current state & gaps

- Suite is **green (56 tests)** as of the 2026-07-27 auth-hardening pass. Covers
  rooms, messages, argon2 hashing + legacy sha256 upgrade, token expiry (sliding
  and absolute), logout/revocation, rate limiting, token-derived REST identity,
  and HTTPS enforcement.
- `pytest.raises(Exception)` has been replaced with `ChatAPIError` throughout.
- **Remaining gap: no socket tests.** `socket.py` is exercised only by the
  manual smoke test, not by pytest. Flask-SocketIO ships
  `socketio.test_client(app)` — worth adding for: connect rejected without a
  token, identity ignored from the payload, and re-verification dropping a
  revoked session mid-connection.
- No tests for `client/chat_client.py`.
