import hashlib

import pytest

from chat import config
from chat.api import ChatAPI
from chat.errors import ChatAPIError


@pytest.fixture
def chat_api(redis):
    return ChatAPI(redis)


class TestRooms:
    def test_get_rooms_empty(self, chat_api):
        assert chat_api.get_rooms() == []

    def test_get_rooms(self, chat_api, redis):
        redis.seed_rooms()
        assert len(chat_api.get_rooms()) == 3

    def test_join_room_valid_user(self, chat_api, redis):
        redis.seed_rooms()
        chat_api.join_room(1, "valid-name")

    def test_join_room_invalid_user(self, chat_api, redis):
        redis.seed_rooms()
        with pytest.raises(ChatAPIError):
            chat_api.join_room(1, "invalid!#name")


class TestRegisterAndLogin:
    def test_register_and_login(self, chat_api):
        chat_api.register_user("alice", "secret")
        token = chat_api.login_user("alice", "secret")
        assert isinstance(token, str)
        assert chat_api.verify_token(token) == "alice"

    def test_login_wrong_password(self, chat_api):
        chat_api.register_user("bob", "pw1")
        with pytest.raises(ChatAPIError):
            chat_api.login_user("bob", "pw2")

    def test_login_unknown_user(self, chat_api):
        with pytest.raises(ChatAPIError):
            chat_api.login_user("nobody", "pw")

    def test_register_duplicate(self, chat_api):
        chat_api.register_user("carol", "pw")
        with pytest.raises(ChatAPIError):
            chat_api.register_user("carol", "pw")

    def test_each_login_issues_a_distinct_token(self, chat_api):
        chat_api.register_user("dave", "pw")
        assert chat_api.login_user("dave", "pw") != chat_api.login_user("dave", "pw")


class TestPasswordHashing:
    def test_password_is_not_stored_as_sha256(self, chat_api, redis):
        chat_api.register_user("erin", "secret")
        stored = redis.hget("users", "erin").decode()
        assert stored != hashlib.sha256(b"secret").hexdigest()
        assert stored.startswith("$argon2")

    def test_same_password_gets_different_hashes(self, chat_api, redis):
        chat_api.register_user("frank", "same-pw")
        chat_api.register_user("grace", "same-pw")
        assert redis.hget("users", "frank") != redis.hget("users", "grace")

    def test_legacy_sha256_hash_still_authenticates(self, chat_api, redis):
        # Simulate a user registered before the argon2 migration.
        redis.hset("users", "heidi", hashlib.sha256(b"old-pw").hexdigest())
        token = chat_api.login_user("heidi", "old-pw")
        assert chat_api.verify_token(token) == "heidi"

    def test_legacy_hash_is_upgraded_on_login(self, chat_api, redis):
        redis.hset("users", "ivan", hashlib.sha256(b"old-pw").hexdigest())
        chat_api.login_user("ivan", "old-pw")
        assert redis.hget("users", "ivan").decode().startswith("$argon2")

    def test_legacy_hash_rejects_wrong_password(self, chat_api, redis):
        redis.hset("users", "judy", hashlib.sha256(b"old-pw").hexdigest())
        with pytest.raises(ChatAPIError):
            chat_api.login_user("judy", "wrong-pw")


class TestTokenExpiry:
    def test_token_expires_after_ttl(self, chat_api, redis, monkeypatch):
        monkeypatch.setattr(config, "TOKEN_TTL", 60)
        chat_api.register_user("kim", "pw")
        token = chat_api.login_user("kim", "pw")

        redis.advance(61)
        with pytest.raises(ChatAPIError):
            chat_api.verify_token(token)

    def test_token_survives_within_ttl(self, chat_api, redis, monkeypatch):
        monkeypatch.setattr(config, "TOKEN_TTL", 60)
        chat_api.register_user("lars", "pw")
        token = chat_api.login_user("lars", "pw")

        redis.advance(30)
        assert chat_api.verify_token(token) == "lars"

    def test_sliding_expiry_refreshes_ttl_on_use(self, chat_api, redis, monkeypatch):
        monkeypatch.setattr(config, "TOKEN_TTL", 60)
        monkeypatch.setattr(config, "TOKEN_SLIDING_EXPIRY", True)
        chat_api.register_user("mia", "pw")
        token = chat_api.login_user("mia", "pw")

        # Keep using the token past the original expiry; it stays valid.
        for _ in range(4):
            redis.advance(40)
            assert chat_api.verify_token(token) == "mia"

        # Once idle for longer than the TTL it lapses.
        redis.advance(61)
        with pytest.raises(ChatAPIError):
            chat_api.verify_token(token)

    def test_absolute_expiry_when_sliding_disabled(self, chat_api, redis, monkeypatch):
        monkeypatch.setattr(config, "TOKEN_TTL", 60)
        monkeypatch.setattr(config, "TOKEN_SLIDING_EXPIRY", False)
        chat_api.register_user("nina", "pw")
        token = chat_api.login_user("nina", "pw")

        redis.advance(40)
        assert chat_api.verify_token(token) == "nina"
        redis.advance(40)
        with pytest.raises(ChatAPIError):
            chat_api.verify_token(token)

    def test_empty_token_is_rejected(self, chat_api):
        with pytest.raises(ChatAPIError):
            chat_api.verify_token("")

    def test_unknown_token_is_rejected(self, chat_api):
        with pytest.raises(ChatAPIError):
            chat_api.verify_token("not-a-real-token")


class TestLogout:
    def test_logout_revokes_token(self, chat_api):
        chat_api.register_user("olga", "pw")
        token = chat_api.login_user("olga", "pw")
        assert chat_api.verify_token(token) == "olga"

        chat_api.logout_user(token)
        with pytest.raises(ChatAPIError):
            chat_api.verify_token(token)

    def test_logout_does_not_affect_other_sessions(self, chat_api):
        chat_api.register_user("pete", "pw")
        first = chat_api.login_user("pete", "pw")
        second = chat_api.login_user("pete", "pw")

        chat_api.logout_user(first)
        assert chat_api.verify_token(second) == "pete"

    def test_logout_is_idempotent(self, chat_api):
        chat_api.logout_user("never-existed")


class TestRateLimiting:
    def test_repeated_failures_are_rate_limited(self, chat_api, monkeypatch):
        monkeypatch.setattr(config, "LOGIN_RATE_LIMIT", 3)
        chat_api.register_user("quinn", "pw")

        for _ in range(3):
            with pytest.raises(ChatAPIError) as exc:
                chat_api.login_user("quinn", "wrong")
            assert exc.value.get_status_code() == 401

        # The next attempt is refused before the password is even checked.
        with pytest.raises(ChatAPIError) as exc:
            chat_api.login_user("quinn", "wrong")
        assert exc.value.get_status_code() == 429

    def test_rate_limit_blocks_even_the_correct_password(self, chat_api, monkeypatch):
        monkeypatch.setattr(config, "LOGIN_RATE_LIMIT", 2)
        chat_api.register_user("rita", "pw")

        for _ in range(2):
            with pytest.raises(ChatAPIError):
                chat_api.login_user("rita", "wrong")
        with pytest.raises(ChatAPIError) as exc:
            chat_api.login_user("rita", "pw")
        assert exc.value.get_status_code() == 429

    def test_window_expiry_resets_the_counter(self, chat_api, redis, monkeypatch):
        monkeypatch.setattr(config, "LOGIN_RATE_LIMIT", 2)
        monkeypatch.setattr(config, "LOGIN_RATE_WINDOW", 60)
        chat_api.register_user("sam", "pw")

        for _ in range(2):
            with pytest.raises(ChatAPIError):
                chat_api.login_user("sam", "wrong")

        redis.advance(61)
        assert isinstance(chat_api.login_user("sam", "pw"), str)

    def test_successful_login_clears_the_counter(self, chat_api, monkeypatch):
        monkeypatch.setattr(config, "LOGIN_RATE_LIMIT", 3)
        chat_api.register_user("tara", "pw")

        with pytest.raises(ChatAPIError):
            chat_api.login_user("tara", "wrong")
        chat_api.login_user("tara", "pw")

        # Counter was reset, so a full budget of attempts is available again.
        for _ in range(3):
            with pytest.raises(ChatAPIError) as exc:
                chat_api.login_user("tara", "wrong")
            assert exc.value.get_status_code() == 401

    def test_rate_limit_can_be_disabled(self, chat_api, monkeypatch):
        monkeypatch.setattr(config, "LOGIN_RATE_LIMIT", 0)
        chat_api.register_user("umar", "pw")

        for _ in range(10):
            with pytest.raises(ChatAPIError) as exc:
                chat_api.login_user("umar", "wrong")
            assert exc.value.get_status_code() == 401

    def test_client_ip_has_its_own_budget(self, chat_api, monkeypatch):
        monkeypatch.setattr(config, "LOGIN_RATE_LIMIT", 10)
        monkeypatch.setattr(config, "LOGIN_RATE_LIMIT_PER_IP", 3)
        chat_api.register_user("vera", "pw")
        chat_api.register_user("walt", "pw")

        # Spreading failures across usernames still trips the per-IP counter,
        # even though no single username reached its own limit.
        for name in ("vera", "walt", "vera"):
            with pytest.raises(ChatAPIError) as exc:
                chat_api.login_user(name, "wrong", client_ip="10.0.0.1")
            assert exc.value.get_status_code() == 401

        with pytest.raises(ChatAPIError) as exc:
            chat_api.login_user("walt", "wrong", client_ip="10.0.0.1")
        assert exc.value.get_status_code() == 429

    def test_other_ips_are_unaffected(self, chat_api, monkeypatch):
        monkeypatch.setattr(config, "LOGIN_RATE_LIMIT", 10)
        monkeypatch.setattr(config, "LOGIN_RATE_LIMIT_PER_IP", 2)
        chat_api.register_user("xena", "pw")

        for _ in range(3):
            with pytest.raises(ChatAPIError):
                chat_api.login_user("xena", "wrong", client_ip="10.0.0.1")

        assert isinstance(chat_api.login_user("xena", "pw", client_ip="10.0.0.2"), str)

    def test_many_users_behind_one_ip_are_not_locked_out(self, chat_api, monkeypatch):
        """Successful logins must not exhaust the shared per-IP budget.

        Everything behind the nginx proxy shares one address, so counting
        successes here would lock out every user after the first few.
        """
        monkeypatch.setattr(config, "LOGIN_RATE_LIMIT_PER_IP", 5)
        names = [f"user{i}" for i in range(12)]
        for name in names:
            chat_api.register_user(name, "pw")

        for name in names:
            assert isinstance(
                chat_api.login_user(name, "pw", client_ip="10.0.0.9"), str
            )


class TestMessages:
    def test_send_and_get_messages(self, chat_api, redis):
        redis.seed_rooms()
        chat_api.send_message(1, "alice", "hello")
        messages = chat_api.get_messages(1)
        assert len(messages) == 1
        assert messages[0]["sender_id"] == "alice"
        assert messages[0]["message"] == "hello"

    def test_send_message_invalid_sender(self, chat_api, redis):
        redis.seed_rooms()
        with pytest.raises(ChatAPIError):
            chat_api.send_message(1, "bad!name", "hello")
