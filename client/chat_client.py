import os
import threading

import requests
import socketio

SERVER_URL = os.environ.get("CHAT_SERVER_URL", "http://localhost:5002")

sio = socketio.Client()

room = 0
username = ""


@sio.event
def connect():
    sio.emit('join', {'username': username, 'room': room})


@sio.event
def disconnect():
    print("I'm disconnected!")


@sio.event
def message(data):
    """Handle a new message from the server."""
    print(data)


@sio.event
def batch(data):
    """Handle a batch of messages from the server."""
    for item in data["data"]:
        print(f"{item['sender_id']}: {item['message']}")


@sio.event
def error(data):
    """Handle an error message from the server."""
    print(f"Error: {data['data']}")


def get_username():
    while True:
        username = input("Enter your username: ")
        if not username or len(username) < 3 or len(username) > 20:
            print("Username must be between 3 and 20 characters")
        else:
            return username


def choose_room():
    """Select a chat room on start. Send and see messages from this room."""
    rooms_ids = []
    try:
        response = requests.get(f"{SERVER_URL}/rooms", timeout=10)
        response.raise_for_status()

        for i, room in enumerate(response.json()):
            rooms_ids.append(room["id"])
            print(f"{i + 1}. {room['topic']}")
    except (requests.exceptions.JSONDecodeError, KeyError):
        print("Invalid response from server")

    while True:
        try:
            room_id = int(input("Choose a chat room by entering its #: "))
            return rooms_ids[room_id - 1]
        except (ValueError, IndexError):
            print("Invalid room id")


def send_messages():
    """Send messages to the server. Input is taken from the console."""
    while True:
        try:
            new_message = input("")
        except (EOFError, KeyboardInterrupt):
            # Ctrl-D / Ctrl-C, or piped input running out: leave the room quietly.
            sio.disconnect()
            return
        print("\033[A \033[A")  # clear the input line
        data = {"username": username, "message": new_message, "room_id": room}
        sio.emit("message", data)


def main():
    global username
    global room
    try:
        username = get_username()
        room = choose_room()

        sio.connect(SERVER_URL)
        input_thread = threading.Thread(target=send_messages)
        input_thread.daemon = True
        input_thread.start()

        sio_thread = threading.Thread(target=sio.wait)
        sio_thread.start()

        input_thread.join()
        sio_thread.join()
    except (KeyboardInterrupt, EOFError):
        # Ctrl-C / Ctrl-D at one of the prompts.
        sio.disconnect()


if __name__ == "__main__":
    main()
