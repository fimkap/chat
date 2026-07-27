from flask import request
from flask_socketio import emit, join_room, leave_room, send

from .errors import ChatAPIError
from .logger import logger
from .routes import chat_api

# Map a WebSocket session ID to the user and room that it joined.
user_sessions = {}

# Map an authenticated WebSocket session ID to its verified username. Populated
# at connect time from the auth token; the socket's identity comes from here,
# never from client-supplied `data["username"]`.
authenticated_users = {}


def handle_connect(auth):
    """Authenticate a new socket connection via its auth token.

    Returning ``False`` rejects the connection, so an unauthenticated client
    is never able to join a room or send messages.
    """
    token = (auth or {}).get("token", "")
    try:
        username = chat_api.verify_token(token)
    except ChatAPIError:
        logger.warning("Rejected unauthenticated socket connection")
        return False
    authenticated_users[request.sid] = username
    logger.info(f"Client connected: {username}")
    emit("connected", {"data": "Connected"})
    return None


def handle_disconnect():
    """Handle a socket disconnection."""
    info = user_sessions.pop(request.sid, None)
    authenticated_users.pop(request.sid, None)
    if info:
        room = info["room"]
        username = info["username"]
        leave_room(room)
        send(f"{username} has left the room.", to=room)
    logger.info("Client disconnected")


def on_join(data):
    username = authenticated_users.get(request.sid)
    if not username:
        emit("error", {"data": "Unauthorized"})
        return
    room = data['room']
    logger.info(f"{username} joining room {room}")
    join_room(room)
    # Track which user/room are associated with this connection
    user_sessions[request.sid] = {
        "username": username,
        "room": room,
    }
    send(f"{username} has entered the room.", to=room)
    try:
        messages = chat_api.get_messages(room)
        emit("batch", {"data": messages})
    except ChatAPIError as e:
        emit("error", {"data": str(e)})


def on_leave(data):
    username = authenticated_users.get(request.sid)
    if not username:
        emit("error", {"data": "Unauthorized"})
        return
    room = data['room']
    leave_room(room)
    # Remove the session mapping if it matches this connection
    user_sessions.pop(request.sid, None)
    send(f"{username} has left the room.", to=room)


def handle_message(data):
    username = authenticated_users.get(request.sid)
    if not username:
        emit("error", {"data": "Unauthorized"})
        return
    room = data["room_id"]
    message = data["message"]
    logger.info(f"Received message from {username} in room {room}")
    try:
        chat_api.send_message(room, username, message)
        send(f"{username}: {message}", to=room, broadcast=True)
    except ChatAPIError as e:
        emit("error", {"data": str(e)})
