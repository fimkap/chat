from flask_socketio import emit, join_room, leave_room, send
from flask import request

from .routes import chat_api
from .logger import logger
from .errors import ChatAPIError

# Map a WebSocket session ID to the user and room that it joined.
user_sessions = {}


def handle_connect():
    logger.info("Client connected")
    """Handle a new socket connection."""
    emit("connected", {"data": "Connected"})


def handle_disconnect():
    """Handle a socket disconnection."""
    info = user_sessions.pop(request.sid, None)
    if info:
        room = info["room"]
        username = info["username"]
        leave_room(room)
        send(username + ' has left the room.', to=room)
    logger.info("Client disconnected")


def on_join(data):
    logger.info(f"Received join request: {data}")
    username = data['username']
    room = data['room']
    join_room(room)
    # Track which user/room are associated with this connection
    user_sessions[request.sid] = {
        "username": username,
        "room": room,
    }
    send(username + ' has entered the room.', to=room)
    try:
        messages = chat_api.get_messages(room)
        emit("batch", {"data": messages})
    except ChatAPIError as e:
        emit("error", {"data": str(e)})


def on_leave(data):
    username = data['username']
    room = data['room']
    leave_room(room)
    # Remove the session mapping if it matches this connection
    user_sessions.pop(request.sid, None)
    send(username + ' has left the room.', to=room)


def handle_message(data):
    logger.info(f"Received message: {data}")
    room = data["room_id"]
    username = data["username"]
    message = data["message"]
    try:
        chat_api.send_message(room, username, message)
        send(username + ": " + message, to=room, broadcast=True)
    except ChatAPIError as e:
        emit("error", {"data": str(e)})
