from flask import Flask
from flask_socketio import SocketIO

from chat.config import CORS_ORIGINS, DEBUG, HOST, PORT, SECRET_KEY
from chat.routes import bp, init_rooms
from chat.socket import (
    handle_connect,
    handle_disconnect,
    handle_message,
    on_join,
    on_leave,
)

app = Flask(__name__)
app.config["SECRET_KEY"] = SECRET_KEY
app.register_blueprint(bp)

# "threading" mode + simple-websocket: no eventlet/gevent monkey-patching.
# Served by gunicorn's gthread worker in Docker (see Dockerfile).
# Only widen socket CORS when CHAT_CORS_ORIGINS is set; the library default is
# same-origin, which is what we want until a browser UI on another origin exists.
socketio_options = {}
if CORS_ORIGINS:
    socketio_options["cors_allowed_origins"] = (
        "*" if CORS_ORIGINS == ["*"] else CORS_ORIGINS
    )

socketio = SocketIO(app, async_mode="threading", **socketio_options)

socketio.on_event("connect", handle_connect)
socketio.on_event("disconnect", handle_disconnect)
socketio.on_event("join", on_join)
socketio.on_event("leave", on_leave)
socketio.on_event("message", handle_message)

init_rooms()

if __name__ == "__main__":
    socketio.run(app, host=HOST, port=PORT, debug=DEBUG, allow_unsafe_werkzeug=True)
