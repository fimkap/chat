import hashlib
import hmac
import json
import time
import uuid

from argon2 import PasswordHasher
from argon2.exceptions import (
    HashingError,
    InvalidHashError,
    VerificationError,
    VerifyMismatchError,
)
from pydantic import ValidationError

try:
    from redis import RedisError
except ImportError:  # pragma: no cover - redis might not be installed

    class RedisError(Exception):
        pass


from . import config
from .errors import ChatAPIError
from .logger import logger
from .models import Message, User

# Argon2id with the library defaults (the current OWASP-recommended KDF).
# Salting is automatic and embedded in the resulting hash string.
_password_hasher = PasswordHasher()

# One Redis key per token, so the server can expire tokens natively.
TOKEN_KEY_PREFIX = "token:"

# Pre-argon2 users have an unsalted sha256 hex digest (64 hex chars) stored.
# Those are verified once, then transparently upgraded on next login.
_LEGACY_HASH_LEN = 64
_HEX_DIGITS = set("0123456789abcdef")

# Cap on how much caller-supplied text becomes part of a rate-limit key.
_RATE_LIMIT_ID_MAX_LEN = 64


class ChatAPI:
    """Internal Chat API."""

    def __init__(self, redis):
        self.redis = redis

    # ------------------------------------------------------------------
    # Password hashing helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _is_legacy_hash(stored: str) -> bool:
        """Report whether a stored hash is a pre-argon2 unsalted sha256 digest."""
        return len(stored) == _LEGACY_HASH_LEN and set(stored) <= _HEX_DIGITS

    def _hash_password(self, password: str) -> str:
        """Hash a password with argon2id.

        Raises:
            ChatAPIError: If hashing fails.
        """
        try:
            return _password_hasher.hash(password)
        except HashingError as e:
            raise ChatAPIError("Error hashing password", 500) from e

    def _verify_password(self, stored: str, password: str) -> tuple[bool, str | None]:
        """Check a password against a stored hash.

        Args:
            stored: The hash currently held in Redis (argon2 or legacy sha256).
            password: The candidate password.

        Returns:
            A ``(ok, upgraded_hash)`` pair. ``upgraded_hash`` is a replacement
            hash to persist when the stored one is legacy or uses outdated
            argon2 parameters, otherwise ``None``.
        """
        if self._is_legacy_hash(stored):
            legacy = hashlib.sha256(password.encode()).hexdigest()
            if hmac.compare_digest(legacy, stored):
                return True, self._hash_password(password)
            return False, None

        try:
            _password_hasher.verify(stored, password)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return False, None

        if _password_hasher.check_needs_rehash(stored):
            return True, self._hash_password(password)
        return True, None

    # ------------------------------------------------------------------
    # Rate limiting
    # ------------------------------------------------------------------

    def _enforce_rate_limit(self, scope: str, identifier: str, limit: int) -> None:
        """Reject a caller that exceeded the attempt budget for a fixed window.

        Uses a Redis counter keyed by scope + identifier that expires after
        ``config.LOGIN_RATE_WINDOW`` seconds. Attempts are counted before the
        password is checked, so a flood cannot force repeated argon2 hashing.

        Args:
            scope: Logical bucket, e.g. ``"login"`` or ``"login-ip"``.
            identifier: Username or client address to count against.
            limit: Attempts allowed in the window; 0 or less disables the check.

        Raises:
            ChatAPIError: 429 once the limit is exceeded.
        """
        if limit <= 0 or config.LOGIN_RATE_LIMIT <= 0 or not identifier:
            return

        key = f"ratelimit:{scope}:{identifier[:_RATE_LIMIT_ID_MAX_LEN]}"
        try:
            attempts = self.redis.incr(key)
            if attempts == 1:
                self.redis.expire(key, config.LOGIN_RATE_WINDOW)
        except RedisError as e:
            raise ChatAPIError("Error checking rate limit", 429) from e

        if attempts > limit:
            logger.warning("Rate limit exceeded for %s:%s", scope, identifier)
            raise ChatAPIError("Too many attempts, try again later", 429)

    def _clear_rate_limit(self, scope: str, identifier: str) -> None:
        """Drop a rate-limit counter after a successful attempt."""
        if not identifier:
            return
        try:
            self.redis.delete(
                f"ratelimit:{scope}:{identifier[:_RATE_LIMIT_ID_MAX_LEN]}"
            )
        except RedisError as e:  # pragma: no cover - best effort only
            logger.warning("Could not clear rate limit for %s: %s", identifier, e)

    # ------------------------------------------------------------------
    # User Authentication helpers
    # ------------------------------------------------------------------

    def register_user(
        self, username: str, password: str, client_ip: str | None = None
    ) -> None:
        """Register a new user.

        Args:
            username: The user's name
            password: The user's password
            client_ip: Caller address, counted against the rate limit

        Raises:
            ChatAPIError: If the user already exists, data is invalid, or the
                caller is rate limited.
        """
        self._enforce_rate_limit(
            "register-ip", client_ip, config.REGISTER_RATE_LIMIT_PER_IP
        )
        try:
            user = User(name=username)
            if self.redis.hexists("users", user.name):
                raise ChatAPIError("User already exists", 400)
            self.redis.hset("users", user.name, self._hash_password(password))
        except (RedisError, ValidationError) as e:
            raise ChatAPIError("Error registering user", 422) from e

    def login_user(
        self, username: str, password: str, client_ip: str | None = None
    ) -> str:
        """Authenticate a user and return a token.

        Verifies the password (upgrading a legacy hash in place when needed) and
        issues an opaque token that expires after ``config.TOKEN_TTL`` seconds.

        Args:
            username: The user's name
            password: The user's password
            client_ip: Caller address, counted against the rate limit

        Returns:
            A newly minted authentication token.

        Raises:
            ChatAPIError: On invalid credentials (401) or rate limiting (429).
        """
        # Rate limit before validation so malformed-username floods count too.
        self._enforce_rate_limit("login", username, config.LOGIN_RATE_LIMIT)
        self._enforce_rate_limit("login-ip", client_ip, config.LOGIN_RATE_LIMIT_PER_IP)

        try:
            user = User(name=username)
            stored = self.redis.hget("users", user.name)
            if not stored:
                raise ChatAPIError("Invalid credentials", 401)

            ok, upgraded = self._verify_password(stored.decode("utf-8"), password)
            if not ok:
                raise ChatAPIError("Invalid credentials", 401)
            if upgraded:
                self.redis.hset("users", user.name, upgraded)
                logger.info("Upgraded password hash for %s", user.name)

            token = str(uuid.uuid4())
            self.redis.set(self._token_key(token), user.name, ex=config.TOKEN_TTL)
        except (RedisError, ValidationError) as e:
            raise ChatAPIError("Error logging in", 401) from e

        # A successful login clears both counters, so only *failed* attempts
        # accumulate. Without this, users behind one address (everything behind
        # the nginx proxy) would exhaust the shared per-IP budget.
        self._clear_rate_limit("login", username)
        self._clear_rate_limit("login-ip", client_ip)
        return token

    @staticmethod
    def _token_key(token: str) -> str:
        """Return the Redis key holding a token's owner."""
        return f"{TOKEN_KEY_PREFIX}{token}"

    def verify_token(self, token: str) -> str:
        """Return the username for an authentication token.

        Refreshes the token's TTL when ``config.TOKEN_SLIDING_EXPIRY`` is set,
        so an actively used token stays valid and an idle one expires.

        Args:
            token: The token presented by the caller.

        Returns:
            The username the token belongs to.

        Raises:
            ChatAPIError: 401 if the token is missing, expired, or revoked.
        """
        if not token:
            raise ChatAPIError("Unauthorized", 401)
        try:
            name = self.redis.get(self._token_key(token))
            if not name:
                raise ChatAPIError("Unauthorized", 401)
            if config.TOKEN_SLIDING_EXPIRY:
                self.redis.expire(self._token_key(token), config.TOKEN_TTL)
            return name.decode("utf-8")
        except RedisError as e:
            raise ChatAPIError("Unauthorized", 401) from e

    def logout_user(self, token: str) -> None:
        """Revoke an authentication token.

        Args:
            token: The token to invalidate.

        Raises:
            ChatAPIError: If the token could not be revoked.
        """
        try:
            self.redis.delete(self._token_key(token))
        except RedisError as e:
            raise ChatAPIError("Error logging out", 500) from e

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
