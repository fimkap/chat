from flask import jsonify, request, Blueprint
from redis import Redis, RedisError
from pydantic import ValidationError
import time
import json
from .models import Message, ChatRoom
from .logger import logger

chat_bp = Blueprint("chat", __name__)

redis = Redis(host="redis", port=6379)


@chat_bp.route("/rooms", methods=["GET"])
def get_rooms():
    """Get all chat rooms.

    Returns:
        A JSON object containing the chat rooms and a status code.

    """
    try:
        rooms = redis.smembers("rooms")
        rooms_decoded = [json.loads(room.decode("utf-8")) for room in rooms]
        logger.info("Got %d chat rooms" % len(rooms_decoded))
        return jsonify(rooms_decoded), 200
    except (RedisError, json.JSONDecodeError) as e:
        logger.error("Error getting chat rooms: %s" % e)
        return jsonify({"error": "Internal Server Error"}), 500


@chat_bp.route("/rooms/<room_id>/users/<user_id>", methods=["POST"])
def join_room(room_id, user_id):
    """Join a chat room.

    Args:
        room_id: str
        user_id: str

    Returns:
        A JSON object containing a success message and a status code.

    """
    try:
        if not redis.sismember("rooms_ids", room_id):
            return jsonify({"error": "Room does not exist"}), 404

        redis.sadd("room:%s:users" % room_id, user_id)
        logger.info("User %s joined room %s" % (user_id, room_id))
    except RedisError as e:
        logger.error("Error joining room: %s" % e)
        return jsonify({"error": "Internal Server Error"}), 500

    return jsonify({"success": True}), 201


@chat_bp.route("/rooms/<room_id>/messages", methods=["POST"])
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

    logger.info("Got message from: %s to room: %s" % (sender_id, room_id))

    # TODO: use pydantic to validate the message
    json_message = json.dumps(
        {"sender_id": sender_id, "timestamp": time.time(), "message": message}
    )
    message_id = redis.zadd(
        "room:%s" % room_id, {json_message: time.time()}, nx=True
    )
    return jsonify(message_id), 201


@chat_bp.route("/rooms/<room_id>/messages", methods=["GET"])
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
        messages = redis.zrange("room:%s" % room_id, 0, -1)
        messages_decoded = [json.loads(message.decode("utf-8")) for message in messages]
        logger.info("Got %d messages from room: %s" % (len(messages_decoded), room_id))
        return jsonify(messages_decoded), 200
    except (RedisError, json.JSONDecodeError) as e:
        logger.error("Error getting messages from room: %s" % e)
        return jsonify({"error": "Internal Server Error"}), 500


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
