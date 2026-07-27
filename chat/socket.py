from flask import request
from flask_socketio import disconnect, emit, join_room, leave_room, send

from .errors import ChatAPIError
from .logger import logger
from .routes import chat_api

# Map a WebSocket session ID to the user and room that it joined.
user_sessions = {}

# Map an authenticated WebSocket session ID to {"username", "token"}. Populated
# at connect time from the auth token. A socket's identity comes from here,
# never from client-supplied `data["username"]`.
authenticated_users = {}


def handle_connect(auth):
    """Authenticate a new socket connection via its auth token.

    Returning ``False`` rejects the connection, so an unauthenticated client is
    never able to join a room or send messages.
    """
    token = (auth or {}).get("token", "")
    try:
        username = chat_api.verify_token(token)
    except ChatAPIError:
        logger.warning("Rejected unauthenticated socket connection")
        return False
    authenticated_users[request.sid] = {"username": username, "token": token}
    logger.info("Client connected: %s", username)
    emit("connected", {"data": "Connected"})
    return None


def current_username():
    """Re-verify this connection's token and return its owner.

    Checked on every event, not just at connect, so a token that expires or is
    revoked mid-session stops working on the already-open socket.

    Returns:
        The authenticated username, or None if the session is unknown or the
        token is no longer valid.
    """
    session = authenticated_users.get(request.sid)
    if not session:
        return None
    try:
        username = chat_api.verify_token(session["token"])
    except ChatAPIError:
        logger.info("Token no longer valid for %s", session["username"])
        return None
    if username != session["username"]:
        # Token was reissued to a different user; treat the session as invalid.
        return None
    return username


def reject_unauthenticated():
    """Tell the client it is not authenticated and close the connection."""
    emit("error", {"data": "Unauthorized"})
    disconnect()


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
    """Join the authenticated user to a room and replay its history."""
    username = current_username()
    if not username:
        reject_unauthenticated()
        return
    room = data["room"]
    logger.info("%s joining room %s", username, room)
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
    """Remove the authenticated user from a room."""
    username = current_username()
    if not username:
        reject_unauthenticated()
        return
    room = data["room"]
    leave_room(room)
    # Remove the session mapping if it matches this connection
    user_sessions.pop(request.sid, None)
    send(f"{username} has left the room.", to=room)


def handle_message(data):
    """Persist and broadcast a message from the authenticated user."""
    username = current_username()
    if not username:
        reject_unauthenticated()
        return
    room = data["room_id"]
    message = data["message"]
    logger.info("Received message from %s in room %s", username, room)
    try:
        chat_api.send_message(room, username, message)
        send(f"{username}: {message}", to=room, broadcast=True)
    except ChatAPIError as e:
        emit("error", {"data": str(e)})
