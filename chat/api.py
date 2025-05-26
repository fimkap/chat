import json
from redis import RedisError
from pydantic import ValidationError
import time
import uuid
import hashlib
from .errors import ChatAPIError
from .models import Message, ChatRoom, User


class ChatAPI:
    """Internal Chat API."""

    def __init__(self, redis):
        self.redis = redis

    # ------------------------------------------------------------------
    # User Authentication helpers
    # ------------------------------------------------------------------

    def register_user(self, username: str, password: str):
        """Register a new user.

        Args:
            username: The user's name
            password: The user's password

        Raises:
            ChatAPIError: If the user already exists or data is invalid
        """
        try:
            user = User(name=username)
            if self.redis.hexists("users", user.name):
                raise ChatAPIError("User already exists", 400)
            hashed = hashlib.sha256(password.encode()).hexdigest()
            self.redis.hset("users", user.name, hashed)
        except (RedisError, ValidationError) as e:
            raise ChatAPIError("Error registering user", 422) from e

    def login_user(self, username: str, password: str) -> str:
        """Authenticate a user and return a token."""
        try:
            user = User(name=username)
            stored = self.redis.hget("users", user.name)
            if not stored:
                raise ChatAPIError("Invalid credentials", 401)
            hashed = hashlib.sha256(password.encode()).hexdigest()
            if stored.decode("utf-8") != hashed:
                raise ChatAPIError("Invalid credentials", 401)
            token = str(uuid.uuid4())
            self.redis.hset("tokens", token, user.name)
            return token
        except (RedisError, ValidationError) as e:
            raise ChatAPIError("Error logging in", 401) from e

    def verify_token(self, token: str) -> str:
        """Return the username for an authentication token."""
        try:
            name = self.redis.hget("tokens", token)
            if not name:
                raise ChatAPIError("Unauthorized", 401)
            return name.decode("utf-8")
        except RedisError as e:
            raise ChatAPIError("Unauthorized", 401) from e

    def get_rooms(self):
        """Get all chat rooms.

        Returns:
            An object containing the chat rooms.

        Raises:
            ChatAPIError: An error occurred while getting the chat rooms.

        """
        try:
            rooms = self.redis.smembers("rooms")
            rooms_decoded = [json.loads(room.decode("utf-8")) for room in rooms]
            return rooms_decoded
        except (RedisError, json.JSONDecodeError) as e:
            raise ChatAPIError("Error getting chat rooms") from e

    def join_room(self, room_id, user_id):
        """Join a chat room.

        Args:
            room_id: str
            user_id: str

        Raises:
            ChatAPIError: An error occurred while joining the chat room.

        """
        try:
            if not self.redis.sismember("rooms_ids", room_id):
                raise ChatAPIError("Room does not exist", 404)

            user = User(name=user_id)  # Validate user_id
            self.redis.sadd("room:%s:users" % room_id, user.name)
        except (RedisError, ValidationError) as e:
            raise ChatAPIError("Error joining room", 422) from e

    def leave_room(self, room_id, user_id):
        """Leave a chat room.

        Args:
            room_id: str
            user_id: str

        Raises:
            ChatAPIError: An error occurred while leaving the chat room.

        """
        try:
            if not self.redis.sismember("rooms_ids", room_id):
                raise ChatAPIError("Room does not exist")

            user = User(name=user_id)  # Validate user_id
            self.redis.srem("room:%s:users" % room_id, user.name)
        except (RedisError, ValidationError) as e:
            raise ChatAPIError("Error leaving room") from e

    def send_message(self, room_id, sender_id, message):
        """Send a message to a chat room.

        Args:
            room_id: str
            sender_id: str
            message: str

        Returns:
            An object containing the message id.

        Raises:
            ChatAPIError: An error occurred while sending the message.

        """
        try:
            user = User(name=sender_id)
            ts = time.time()
            msg = Message(sender_id=user.name, timestamp=ts, message=message)
            message_id = self.redis.zadd(
                "room:%s" % room_id, {json.dumps(msg.model_dump()): ts}, nx=True
            )
        except (ValidationError, RedisError, json.JSONDecodeError) as e:
            raise ChatAPIError("Error sending message", 422) from e

        return message_id

    def get_messages(self, room_id):
        """Get all messages from a chat room.

        Args:
            room_id: str

        Returns:
            An object containing the messages.

        Raises:
            ChatAPIError: An error occurred while getting the messages.

        """
        try:
            messages = self.redis.zrange("room:%s" % room_id, 0, -1)
            messages_decoded = [
                json.loads(message.decode("utf-8")) for message in messages
            ]
            return messages_decoded
        except (RedisError, json.JSONDecodeError) as e:
            raise ChatAPIError("Error getting messages", 422) from e
