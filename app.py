from flask import Flask
from chat.routes import send_message, get_messages

app = Flask(__name__)

app.add_url_rule("/message", view_func=send_message, methods=["POST"])
app.add_url_rule("/message", view_func=get_messages, methods=["GET"])

if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True)
