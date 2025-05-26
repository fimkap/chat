import json
import pytest
from pytest_mock_resources import create_redis_fixture
from chat.api import ChatAPI
from chat.models import ChatRoom

redis = create_redis_fixture()


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
            redis.sadd("rooms", json.dumps(room.model_dump()))
            redis.sadd("rooms_ids", room.id)
