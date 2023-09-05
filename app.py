from flask import Flask
from flask_socketio import SocketIO
from chat.routes import init_rooms, bp
from chat.socket import (
    handle_connect,
    handle_disconnect,
    on_join,
    on_leave,
    handle_message,
)

app = Flask(__name__)
app.config["SECRET_KEY"] = "secret!"
app.register_blueprint(bp)

socketio = SocketIO(app)

socketio.on_event("connect", handle_connect)
socketio.on_event("disconnect", handle_disconnect)
socketio.on_event("join", on_join)
socketio.on_event("leave", on_leave)
socketio.on_event("message", handle_message)

init_rooms()

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", debug=True)
