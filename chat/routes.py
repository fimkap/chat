from flask import jsonify, request, Blueprint
from redis import Redis
from pydantic import ValidationError
import json
from .models import ChatRoom
from .logger import logger
from .api import ChatAPI
from .errors import ChatAPIError

bp = Blueprint("chat", __name__)

redis = Redis(host="redis", port=6379)

chat_api = ChatAPI(redis)


@bp.route("/rooms", methods=["GET"])
def get_rooms():
    """Get all chat rooms.

    Returns:
        A JSON object containing the chat rooms and a status code.

    """
    try:
        rooms = chat_api.get_rooms()
        logger.info("Got %d chat rooms" % len(rooms))
        return jsonify(rooms), 200
    except (ChatAPIError) as e:
        logger.error("Error getting chat rooms: %s" % e)
        return jsonify({"error": "Error getting chat rooms"}), e.get_status_code()


@bp.route("/rooms/<room_id>/users/<user_id>", methods=["POST"])
def join_room(room_id, user_id):
    """Join a chat room.

    Args:
        room_id: str
        user_id: str

    Returns:
        A JSON object containing a success message and a status code.

    """
    try:
        chat_api.join_room(room_id, user_id)
        logger.info("User %s joined room %s" % (user_id, room_id))
        return jsonify({"success": True}), 201
    except ChatAPIError as e:
        logger.error("Error joining room: %s" % e)
        return jsonify({"error": "Error joining room"}), e.get_status_code()


@bp.route("/rooms/<room_id>/messages", methods=["POST"])
def send_message(room_id):
    """Send a message to a chat room.

    Args:
        room_id: str

    Payload:
        {
            "sender_id": str,
            "message": str
        }

    Returns:
        A JSON object containing the message id and a status code.

    """
    try:
        sender_id = request.json["sender_id"]
        message = request.json["message"]
    except (KeyError, TypeError) as e:
        logger.error("Error getting message from request body: %s" % e)
        return jsonify({"error": "Invalid request body format"}), 400

    try:
        message_id = chat_api.send_message(room_id, sender_id, message)
        logger.info("Got message from: %s to room: %s" % (sender_id, room_id))
        return jsonify(message_id), 200
    except ChatAPIError as e:
        logger.error("Error adding message to room: %s" % e)
        return jsonify({"error": "Error sending message"}), e.get_status_code()


@bp.route("/rooms/<room_id>/messages", methods=["GET"])
def get_messages(room_id):
    """Get all messages from a chat room.

    Args:
        room_id: str

    Query Parameters:
        timestamp: float

    Returns:
        A JSON object containing the messages and a status code.

    """
    try:
        messages = chat_api.get_messages(room_id)
        logger.info("Got %d messages from room: %s" % (len(messages), room_id))
        return jsonify(messages), 200
    except ChatAPIError as e:
        logger.error("Error getting messages from room: %s" % e)
        return jsonify({"error": "Error getting messages from room"}), e.get_status_code()


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
    except (ValidationError, json.JSONDecodeError) as e:
        logger.error("Error initializing chat rooms: %s" % e)
