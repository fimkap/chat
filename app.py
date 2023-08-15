from flask import Flask
from flask_socketio import SocketIO, emit, join_room, leave_room, send
from chat.routes import chat_bp, init_rooms, chat_api
from chat.logger import logger
from chat.errors import ChatAPIError

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app)
app.register_blueprint(chat_bp)


# should be moved to another file
@socketio.on("connect")
def handle_connect():
    """Handle a new socket connection."""
    emit("connected", {"data": "Connected"})


@socketio.on("disconnect")
def handle_disconnect():
    """Handle a socket disconnection."""
    pass


@socketio.on('join')
def on_join(data):
    username = data['username']
    room = data['room']
    join_room(room)
    send(username + ' has entered the room.', to=room)
    try:
        messages = chat_api.get_messages(room)
        emit("batch", {"data": messages})
    except ChatAPIError as e:
        emit("error", {"data": str(e)})


@socketio.on('leave')
def on_leave(data):
    username = data['username']
    room = data['room']
    leave_room(room)
    send(username + ' has left the room.', to=room)


@socketio.on("message")
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


init_rooms()

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", debug=True)
