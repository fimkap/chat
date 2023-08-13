from flask import jsonify, request, Blueprint
from redis import Redis, RedisError
import time
import json

chat_bp = Blueprint("chat", __name__)

redis = Redis(host="redis", port=6379)


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
    except KeyError:
        return jsonify({"error": "parameter is missing from the request body"}), 400
    except TypeError:
        return jsonify({"error": "Invalid request body format"}), 400

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
        return jsonify(messages_decoded), 200
    except RedisError:
        return jsonify({"error": "Internal Server Error"}), 500
