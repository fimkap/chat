"""Shared fixtures: an in-memory Redis fake and a fast password hasher.

`FakeRedis` covers only the commands `ChatAPI` uses. It also models key
expiry against a fake clock, so TTL behaviour can be tested without sleeping.
"""

import json

import pytest
from argon2 import PasswordHasher

from chat import api
from chat.models import ChatRoom


class FakeRedis:
    """Minimal in-memory stand-in for the Redis commands ChatAPI uses."""

    def __init__(self):
        self._sets = {}
        self._zsets = {}
        self._hashes = {}
        self._strings = {}
        # key -> absolute expiry, measured against `clock`
        self._expiry = {}
        self.clock = 0.0

    # -- test helpers ---------------------------------------------------

    def advance(self, seconds):
        """Move the fake clock forward so TTLs can lapse."""
        self.clock += seconds

    def flushdb(self):
        self._sets.clear()
        self._zsets.clear()
        self._hashes.clear()
        self._strings.clear()
        self._expiry.clear()

    def seed_rooms(self):
        """Populate the three default rooms."""
        for room in (
            ChatRoom(id=1, topic="cats"),
            ChatRoom(id=2, topic="dogs"),
            ChatRoom(id=3, topic="birds"),
        ):
            self.sadd("rooms", json.dumps(room.model_dump()))
            self.sadd("rooms_ids", room.id)

    # -- internals ------------------------------------------------------

    def _encode(self, value):
        if isinstance(value, bytes):
            return value
        return str(value).encode("utf-8")

    def _stores(self):
        return (self._strings, self._hashes, self._sets, self._zsets)

    def _exists(self, key):
        return any(key in store for store in self._stores())

    def _purge(self, key):
        """Drop a key if its TTL has lapsed."""
        expiry = self._expiry.get(key)
        if expiry is not None and expiry <= self.clock:
            for store in self._stores():
                store.pop(key, None)
            self._expiry.pop(key, None)

    # -- strings --------------------------------------------------------

    def set(self, key, value, ex=None):
        self._strings[key] = self._encode(value)
        if ex is None:
            self._expiry.pop(key, None)
        else:
            self._expiry[key] = self.clock + ex
        return True

    def get(self, key):
        self._purge(key)
        return self._strings.get(key)

    def incr(self, key):
        self._purge(key)
        value = int(self._strings.get(key, b"0")) + 1
        self._strings[key] = self._encode(value)
        return value

    def delete(self, *keys):
        removed = 0
        for key in keys:
            self._expiry.pop(key, None)
            for store in self._stores():
                if store.pop(key, None) is not None:
                    removed += 1
                    break
        return removed

    def expire(self, key, seconds):
        self._purge(key)
        if not self._exists(key):
            return False
        self._expiry[key] = self.clock + seconds
        return True

    def ttl(self, key):
        self._purge(key)
        if not self._exists(key):
            return -2
        expiry = self._expiry.get(key)
        if expiry is None:
            return -1
        return int(expiry - self.clock)

    # -- sets -----------------------------------------------------------

    def sadd(self, key, *values):
        s = self._sets.setdefault(key, set())
        added = 0
        for v in values:
            ev = self._encode(v)
            if ev not in s:
                s.add(ev)
                added += 1
        return added

    def smembers(self, key):
        self._purge(key)
        return set(self._sets.get(key, set()))

    def sismember(self, key, value):
        self._purge(key)
        return self._encode(value) in self._sets.get(key, set())

    def srem(self, key, *values):
        s = self._sets.get(key, set())
        removed = 0
        for v in values:
            ev = self._encode(v)
            if ev in s:
                s.remove(ev)
                removed += 1
        return removed

    # -- hashes ---------------------------------------------------------

    def hset(self, key, field, value):
        h = self._hashes.setdefault(key, {})
        ef = self._encode(field)
        added = 0 if ef in h else 1
        h[ef] = self._encode(value)
        return added

    def hget(self, key, field):
        self._purge(key)
        return self._hashes.get(key, {}).get(self._encode(field))

    def hexists(self, key, field):
        self._purge(key)
        return self._encode(field) in self._hashes.get(key, {})

    def hdel(self, key, *fields):
        h = self._hashes.get(key, {})
        return sum(h.pop(self._encode(f), None) is not None for f in fields)

    # -- sorted sets ----------------------------------------------------

    def zadd(self, key, mapping, nx=False):
        z = self._zsets.setdefault(key, {})
        added = 0
        for member, score in mapping.items():
            em = self._encode(member)
            if nx and em in z:
                continue
            if em not in z:
                added += 1
            z[em] = score
        return added

    def zrange(self, key, start, end):
        self._purge(key)
        z = self._zsets.get(key, {})
        members = [m for m, _ in sorted(z.items(), key=lambda kv: kv[1])]
        if end == -1:
            end = len(members) - 1
        return [members[i] for i in range(start, min(end + 1, len(members)))]


@pytest.fixture(autouse=True, scope="session")
def fast_password_hashing():
    """Swap in cheap argon2 parameters so hashing does not dominate runtime.

    Production keeps the library defaults; only the test process is weakened.
    """
    original = api._password_hasher
    api._password_hasher = PasswordHasher(time_cost=1, memory_cost=8, parallelism=1)
    yield
    api._password_hasher = original


@pytest.fixture
def redis():
    return FakeRedis()
