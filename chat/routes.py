from flask import jsonify, request
from redis import Redis, RedisError
import time
import json

redis = Redis(host="redis", port=6379)


def send_message():
    """Send a message to a user.

    Payload:
        {
            "sender_id": str,
            "receiver_id": str,
            "message": str
        }

    Returns:
        A JSON object containing the message id and a status code.

    """
    try:
        sender_id = request.json["sender_id"]
        receiver_id = request.json["receiver_id"]
        message = request.json["message"]
    except KeyError:
        return jsonify({"error": "parameter is missing from the request body"}), 400
    except TypeError:
        return jsonify({"error": "Invalid request body format"}), 400

    json_message = json.dumps(
        {"sender_id": sender_id, "timestamp": time.time(), "message": message}
    )
    room_key = f"room:{min(sender_id, receiver_id)}:{max(sender_id, receiver_id)}"
    message_id = redis.zadd(
        "room:%s" % room_key, {json_message: time.time()}, nx=True
    )
    return jsonify(message_id), 201


def get_messages():
    """Get all messages between two users.

    Query Parameters:
        user_id: str
        party_id: str

    Returns:
        A JSON object containing the messages and a status code.

    """
    try:
        user_id = request.args["user_id"]
        party_id = request.args["party_id"]
    except KeyError:
        return jsonify({"error": "parameter is missing from the request body"}), 400
    except TypeError:
        return jsonify({"error": "Invalid request body format"}), 400

    room_key = f"room:{min(user_id, party_id)}:{max(user_id, party_id)}"
    try:
        messages = redis.zrange("room:%s" % room_key, 0, -1)
        messages_decoded = [message.decode("utf-8") for message in messages]
        return jsonify(messages_decoded), 200
    except RedisError:
        return jsonify({"error": "Internal Server Error"}), 500
