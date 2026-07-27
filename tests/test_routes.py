"""Flask test_client coverage for the REST auth surface.

Swaps the shared `chat_api`'s Redis for the in-memory fake, so no live Redis
is needed.
"""

import pytest
from flask import Flask

from chat import config, routes


@pytest.fixture
def client(redis, monkeypatch):
    monkeypatch.setattr(routes.chat_api, "redis", redis)
    redis.seed_rooms()

    app = Flask(__name__)
    app.config["SECRET_KEY"] = "test"
    app.register_blueprint(routes.bp)
    return app.test_client()


def auth(token):
    """Build the Authorization header for a token."""
    return {"Authorization": f"Bearer {token}"}


def post(client, path, token=None, **kwargs):
    """POST and return just the status code."""
    headers = auth(token) if token else {}
    return client.post(path, headers=headers, **kwargs).status_code


def get(client, path, token=None):
    """GET and return just the status code."""
    headers = auth(token) if token else {}
    return client.get(path, headers=headers).status_code


def register_and_login(client, username="alice", password="secret"):
    """Create a user and return a valid bearer token."""
    creds = {"username": username, "password": password}
    assert post(client, "/register", json=creds) == 201
    response = client.post("/login", json=creds)
    assert response.status_code == 200
    return response.get_json()["token"]


class TestAuthEnforcement:
    @pytest.mark.parametrize(
        ("method", "path"),
        [
            ("get", "/rooms"),
            ("get", "/rooms/1/messages"),
            ("post", "/rooms/1/messages"),
            ("post", "/rooms/1/users/me"),
            ("post", "/rooms/1/users/alice"),
            ("post", "/logout"),
        ],
    )
    def test_protected_routes_reject_missing_token(self, client, method, path):
        assert getattr(client, method)(path).status_code == 401

    def test_protected_route_rejects_bogus_token(self, client):
        assert get(client, "/rooms", "nope") == 401

    def test_valid_token_is_accepted(self, client):
        token = register_and_login(client)
        assert get(client, "/rooms", token) == 200

    def test_bare_token_without_bearer_prefix_works(self, client):
        token = register_and_login(client)
        response = client.get("/rooms", headers={"Authorization": token})
        assert response.status_code == 200

    def test_register_and_login_need_no_token(self, client):
        creds = {"username": "bob", "password": "pw"}
        assert post(client, "/register", json=creds) == 201
        assert post(client, "/login", json=creds) == 200

    def test_login_reports_token_lifetime(self, client, monkeypatch):
        monkeypatch.setattr(config, "TOKEN_TTL", 1800)
        creds = {"username": "cara", "password": "pw"}
        client.post("/register", json=creds)
        response = client.post("/login", json=creds)
        assert response.get_json()["expires_in"] == 1800


class TestTokenDerivedIdentity:
    def test_message_sender_comes_from_the_token(self, client):
        token = register_and_login(client, "dana")
        assert post(client, "/rooms/1/messages", token, json={"message": "hi"}) == 200

        messages = client.get("/rooms/1/messages", headers=auth(token)).get_json()
        assert [m["sender_id"] for m in messages] == ["dana"]

    def test_cannot_send_as_another_user(self, client):
        token = register_and_login(client, "erin")
        spoofed = {"message": "spoofed", "sender_id": "victim"}
        assert post(client, "/rooms/1/messages", token, json=spoofed) == 401

        messages = client.get("/rooms/1/messages", headers=auth(token)).get_json()
        assert messages == []

    def test_matching_sender_id_is_accepted(self, client):
        token = register_and_login(client, "fred")
        body = {"message": "hi", "sender_id": "fred"}
        assert post(client, "/rooms/1/messages", token, json=body) == 200

    def test_message_requires_a_body(self, client):
        token = register_and_login(client, "gina")
        assert post(client, "/rooms/1/messages", token, json={}) == 400

    def test_join_as_self_succeeds(self, client):
        token = register_and_login(client, "hank")
        assert post(client, "/rooms/1/users/me", token) == 201
        assert post(client, "/rooms/1/users/hank", token) == 201

    def test_cannot_join_as_another_user(self, client):
        token = register_and_login(client, "iris")
        assert post(client, "/rooms/1/users/someone-else", token) == 401


class TestLogoutRoute:
    def test_logout_invalidates_the_token(self, client):
        token = register_and_login(client, "jane")
        assert post(client, "/logout", token) == 200
        assert get(client, "/rooms", token) == 401

    def test_logout_twice_is_rejected_the_second_time(self, client):
        token = register_and_login(client, "karl")
        assert post(client, "/logout", token) == 200
        assert post(client, "/logout", token) == 401


class TestRateLimitedRoutes:
    def test_login_returns_429_when_rate_limited(self, client, monkeypatch):
        monkeypatch.setattr(config, "LOGIN_RATE_LIMIT", 2)
        client.post("/register", json={"username": "lena", "password": "pw"})
        bad = {"username": "lena", "password": "bad"}

        for _ in range(2):
            assert post(client, "/login", json=bad) == 401
        assert post(client, "/login", json=bad) == 429


class TestHttpsEnforcement:
    def test_plaintext_rejected_when_https_required(self, client, monkeypatch):
        monkeypatch.setattr(config, "REQUIRE_HTTPS", True)
        response = client.post("/login", json={"username": "mona", "password": "pw"})
        assert response.status_code == 403
        assert response.get_json()["error"] == "HTTPS required"

    def test_forwarded_https_is_accepted(self, client, monkeypatch):
        token = register_and_login(client, "nora")
        monkeypatch.setattr(config, "REQUIRE_HTTPS", True)
        response = client.get(
            "/rooms",
            headers={**auth(token), "X-Forwarded-Proto": "https"},
        )
        assert response.status_code == 200

    def test_plaintext_allowed_by_default(self, client):
        token = register_and_login(client, "omar")
        assert get(client, "/rooms", token) == 200
