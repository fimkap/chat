import json
import os
import sys
import pytest
from pydantic import ValidationError

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from chat.api import ChatAPI
from chat.models import ChatRoom, User, Message


class FakeRedis:
    def __init__(self):
        self._sets = {}
        self._zsets = {}
        self._hashes = {}

    def flushdb(self):
        self._sets.clear()
        self._zsets.clear()
        self._hashes.clear()

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

    def hexists(self, key, field):
        h = self._hashes.get(key, {})
        return self._encode(field) in h

    def hset(self, key, field, value):
        h = self._hashes.setdefault(key, {})
        ef = self._encode(field)
        ev = self._encode(value)
        was_new = ef not in h
        h[ef] = ev
        return 1 if was_new else 0

    def hget(self, key, field):
        h = self._hashes.get(key, {})
        ef = self._encode(field)
        return h.get(ef)


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

    def test_user_validation(self):
        # Test valid user
        user = User(name="valid_user")
        assert user.name == "valid_user"
        
        # Test invalid user with special characters
        with pytest.raises(ValidationError):
            User(name="invalid!user")
            
        # Test user name too short
        with pytest.raises(ValidationError):
            User(name="ab")
            
        # Test user name too long
        with pytest.raises(ValidationError):
            User(name="a" * 20)

    def test_message_validation(self):
        # Test valid message
        msg = Message(sender_id="test_user", timestamp=123.45, message="Hello world!")
        assert msg.message == "Hello world!"
        
        # Test empty message
        with pytest.raises(ValidationError):
            Message(sender_id="test_user", timestamp=123.45, message="")
            
        # Test message too long
        with pytest.raises(ValidationError):
            Message(sender_id="test_user", timestamp=123.45, message="a" * 200)

    def test_chatroom_validation(self):
        # Test valid chat room
        room = ChatRoom(id=1, topic="valid_topic")
        assert room.topic == "valid_topic"
        
        # Test invalid topic with special characters
        with pytest.raises(ValidationError):
            ChatRoom(id=1, topic="invalid-topic!")
            
        # Test topic too short
        with pytest.raises(ValidationError):
            ChatRoom(id=1, topic="ab")
            
        # Test topic too long
        with pytest.raises(ValidationError):
            ChatRoom(id=1, topic="a" * 30)

    def _init_rooms(self, redis):
        rooms = [
            ChatRoom(id=1, topic="cats"),
            ChatRoom(id=2, topic="dogs"),
            ChatRoom(id=3, topic="birds"),
        ]
        for room in rooms:
            redis.sadd("rooms", json.dumps(room.model_dump()))
            redis.sadd("rooms_ids", room.id)
