import json
from functools import wraps

from flask import Blueprint, g, jsonify, request
from pydantic import ValidationError
from redis import Redis, RedisError

from . import config
from .api import ChatAPI
from .config import REDIS_HOST, REDIS_PORT
from .errors import ChatAPIError
from .logger import logger
from .models import ChatRoom

bp = Blueprint("chat", __name__)

redis = Redis(host=REDIS_HOST, port=REDIS_PORT)

chat_api = ChatAPI(redis)


def client_ip() -> str:
    """Return the caller's address for rate-limiting purposes.

    Prefers the headers set by the bundled nginx config. These are only
    trustworthy when the app is reachable exclusively through that proxy; a
    directly exposed app lets a caller spoof them.

    Returns:
        The client address, or an empty string if it cannot be determined.
    """
    forwarded = request.headers.get("X-Real-IP") or request.headers.get(
        "X-Forwarded-For", ""
    )
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or ""


def bearer_token() -> str:
    """Extract the auth token from the Authorization header.

    Accepts both ``Bearer <token>`` and a bare token.

    Returns:
        The token, or an empty string if the header is absent.
    """
    header = request.headers.get("Authorization", "").strip()
    scheme, _, token = header.partition(" ")
    if scheme.lower() == "bearer":
        return token.strip()
    return header


def require_auth(view):
    """Require a valid token and expose its owner as ``g.username``.

    Identity always comes from the token, never from the request body or path,
    so a caller cannot act as another user.
    """

    @wraps(view)
    def wrapper(*args, **kwargs):
        try:
            g.username = chat_api.verify_token(bearer_token())
        except ChatAPIError as e:
            logger.warning("Unauthorized request to %s", request.path)
            return jsonify({"error": str(e)}), e.get_status_code()
        return view(*args, **kwargs)

    return wrapper


@bp.before_request
def enforce_https():
    """Reject plaintext requests when CHAT_REQUIRE_HTTPS is enabled.

    Relies on the TLS-terminating proxy setting X-Forwarded-Proto.
    """
    if not config.REQUIRE_HTTPS:
        return None
    proto = request.headers.get("X-Forwarded-Proto", request.scheme)
    if proto != "https":
        logger.warning("Rejected plaintext request to %s", request.path)
        return jsonify({"error": "HTTPS required"}), 403
    return None


@bp.route("/register", methods=["POST"])
def register():
    """Register a new user."""
    try:
        username = request.json["username"]
        password = request.json["password"]
    except (KeyError, TypeError):
        return jsonify({"error": "Invalid request"}), 400

    try:
        chat_api.register_user(username, password, client_ip())
        logger.info("Registered user %s", username)
        return jsonify({"success": True}), 201
    except ChatAPIError as e:
        logger.error("Error registering user: %s", e)
        return jsonify({"error": str(e)}), e.get_status_code()


@bp.route("/login", methods=["POST"])
def login():
    """Login a user and return a token.

    Returns:
        A JSON object with the token and its lifetime in seconds.

    """
    try:
        username = request.json["username"]
        password = request.json["password"]
    except (KeyError, TypeError):
        return jsonify({"error": "Invalid request"}), 400

    try:
        token = chat_api.login_user(username, password, client_ip())
        logger.info("User %s logged in", username)
        return jsonify({"token": token, "expires_in": config.TOKEN_TTL}), 200
    except ChatAPIError as e:
        logger.error("Error logging in: %s", e)
        return jsonify({"error": str(e)}), e.get_status_code()


@bp.route("/logout", methods=["POST"])
@require_auth
def logout():
    """Revoke the caller's token.

    Returns:
        A JSON object containing a success message and a status code.

    """
    try:
        chat_api.logout_user(bearer_token())
        logger.info("User %s logged out", g.username)
        return jsonify({"success": True}), 200
    except ChatAPIError as e:
        logger.error("Error logging out: %s", e)
        return jsonify({"error": str(e)}), e.get_status_code()


@bp.route("/rooms", methods=["GET"])
@require_auth
def get_rooms():
    """Get all chat rooms.

    Returns:
        A JSON object containing the chat rooms and a status code.

    """
    try:
        rooms = chat_api.get_rooms()
        logger.info("Got %d chat rooms", len(rooms))
        return jsonify(rooms), 200
    except ChatAPIError as e:
        logger.error("Error getting chat rooms: %s", e)
        return jsonify({"error": "Error getting chat rooms"}), e.get_status_code()


def _join_room_as_authenticated_user(room_id):
    """Add the token owner to a room and build the JSON response."""
    try:
        chat_api.join_room(room_id, g.username)
        logger.info("User %s joined room %s", g.username, room_id)
        return jsonify({"success": True}), 201
    except ChatAPIError as e:
        logger.error("Error joining room: %s", e)
        return jsonify({"error": "Error joining room"}), e.get_status_code()


@bp.route("/rooms/<room_id>/users/me", methods=["POST"])
@require_auth
def join_room(room_id):
    """Join a chat room as the authenticated user.

    Returns:
        A JSON object containing a success message and a status code.

    """
    return _join_room_as_authenticated_user(room_id)


@bp.route("/rooms/<room_id>/users/<user_id>", methods=["POST"])
@require_auth
def join_room_as_user(room_id, user_id):
    """Join a chat room (legacy path that names the user explicitly).

    Prefer ``POST /rooms/<room_id>/users/me``. The named user must match the
    token owner.

    Returns:
        A JSON object containing a success message and a status code.

    """
    if user_id != g.username:
        logger.warning("User %s tried to join as %s", g.username, user_id)
        return jsonify({"error": "Error joining room"}), 401
    return _join_room_as_authenticated_user(room_id)


@bp.route("/rooms/<room_id>/messages", methods=["POST"])
@require_auth
def send_message(room_id):
    """Send a message to a chat room as the authenticated user.

    Args:
        room_id: str

    Payload:
        {
            "message": str
        }

    A ``sender_id`` may be supplied for backwards compatibility but must match
    the token owner; the stored sender always comes from the token.

    Returns:
        A JSON object containing the message id and a status code.

    """
    try:
        message = request.json["message"]
        sender_id = request.json.get("sender_id")
    except (KeyError, TypeError) as e:
        logger.error("Error getting message from request body: %s", e)
        return jsonify({"error": "Invalid request body format"}), 400

    if sender_id is not None and sender_id != g.username:
        logger.warning("User %s tried to send as %s", g.username, sender_id)
        return jsonify({"error": "Error sending message"}), 401

    try:
        message_id = chat_api.send_message(room_id, g.username, message)
        logger.info("Got message from: %s to room: %s", g.username, room_id)
        return jsonify(message_id), 200
    except ChatAPIError as e:
        logger.error("Error adding message to room: %s", e)
        return jsonify({"error": "Error sending message"}), e.get_status_code()


@bp.route("/rooms/<room_id>/messages", methods=["GET"])
@require_auth
def get_messages(room_id):
    """Get all messages from a chat room.

    Args:
        room_id: str

    Returns:
        A JSON object containing the messages and a status code.

    """
    try:
        messages = chat_api.get_messages(room_id)
        logger.info("Got %d messages from room: %s", len(messages), room_id)
        return jsonify(messages), 200
    except ChatAPIError as e:
        logger.error("Error getting messages from room: %s", e)
        return (
            jsonify({"error": "Error getting messages from room"}),
            e.get_status_code(),
        )


def init_rooms():
    """Initialize chat rooms."""
    try:
        rooms = [
            ChatRoom(id=1, topic="cats"),
            ChatRoom(id=2, topic="dogs"),
            ChatRoom(id=3, topic="birds"),
        ]
        for room in rooms:
            redis.sadd("rooms", json.dumps(room.model_dump()))
            redis.sadd("rooms_ids", room.id)
        logger.info("Initialized chat rooms")
    except (ValidationError, json.JSONDecodeError, RedisError) as e:
        # Don't take the whole app down if Redis isn't reachable yet.
        logger.error("Error initializing chat rooms: %s", e)
