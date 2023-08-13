from flask import Flask
from chat.routes import chat_bp

app = Flask(__name__)
app.register_blueprint(chat_bp)


if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True)
