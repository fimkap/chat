import json
import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from chat.api import ChatAPI
from chat.models import ChatRoom


class FakeRedis:
    def __init__(self):
        self._sets = {}
        self._zsets = {}

    def flushdb(self):
        self._sets.clear()
        self._zsets.clear()

    def _encode(self, value):
        if isinstance(value, bytes):
            return value
        return str(value).encode("utf-8")

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
        return set(self._sets.get(key, set()))

    def sismember(self, key, value):
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
        z = self._zsets.get(key, {})
        sorted_members = [m for m, _ in sorted(z.items(), key=lambda kv: kv[1])]
        if end == -1:
            end = len(sorted_members) - 1
        return [sorted_members[i] for i in range(start, min(end + 1, len(sorted_members)))]


@pytest.fixture
def redis():
    return FakeRedis()


class TestChatAPI:
    @pytest.fixture
    def chat_api(self, redis):
        return ChatAPI(redis)

    def test_get_rooms_empty(self, chat_api):
        rooms = chat_api.get_rooms()
        assert rooms == []

    def test_get_rooms(self, chat_api, redis):
        self._init_rooms(redis)
        rooms = chat_api.get_rooms()
        assert len(rooms) == 3

    def test_join_room_valid_user(self, chat_api, redis):
        self._init_rooms(redis)
        chat_api.join_room(1, "valid-name")

    def test_join_room_invalid_user(self, chat_api, redis):
        with pytest.raises(Exception):
            self._init_rooms(redis)
            chat_api.join_room(1, "invalid!#name")

    def test_register_and_login(self, chat_api):
        chat_api.register_user("alice", "secret")
        token = chat_api.login_user("alice", "secret")
        assert isinstance(token, str)
        username = chat_api.verify_token(token)
        assert username == "alice"

    def test_login_wrong_password(self, chat_api):
        chat_api.register_user("bob", "pw1")
        with pytest.raises(Exception):
            chat_api.login_user("bob", "pw2")

    def test_register_duplicate(self, chat_api):
        chat_api.register_user("carol", "pw")
        with pytest.raises(Exception):
            chat_api.register_user("carol", "pw")

    def _init_rooms(self, redis):
        rooms = [
            ChatRoom(id=1, topic="cats"),
            ChatRoom(id=2, topic="dogs"),
            ChatRoom(id=3, topic="birds"),
        ]
        for room in rooms:
            redis.sadd("rooms", json.dumps(room.dict()))
            redis.sadd("rooms_ids", room.id)
