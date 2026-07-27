import getpass
import os
import threading

import requests
import socketio

SERVER_URL = os.environ.get("CHAT_SERVER_URL", "http://localhost:5002")

sio = socketio.Client()

room = 0
username = ""
token = ""


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


def auth_headers():
    """Return the Authorization header carrying the current token."""
    return {"Authorization": f"Bearer {token}"}


def _server_error(response):
    """Extract the server's error message from a failed response."""
    try:
        return response.json().get("error", response.reason)
    except requests.exceptions.JSONDecodeError:
        return response.reason


def authenticate(username):
    """Log the user in (registering first if new) and return an auth token.

    The server enforces authentication on the REST routes and on the WebSocket
    handshake, so without a valid token the client cannot list rooms, join, or
    send messages.
    """
    password = getpass.getpass("Enter your password: ")

    def login():
        return requests.post(
            f"{SERVER_URL}/login",
            json={"username": username, "password": password},
            timeout=10,
        )

    try:
        response = login()
        if response.status_code == 401:
            # Unknown user: register, then log in.
            registered = requests.post(
                f"{SERVER_URL}/register",
                json={"username": username, "password": password},
                timeout=10,
            )
            if registered.status_code != 201:
                print(f"Registration failed: {_server_error(registered)}")
                return None
            response = login()
    except requests.exceptions.RequestException as e:
        print(f"Could not reach server: {e}")
        return None

    if response.status_code == 429:
        print("Too many attempts. Wait a minute and try again.")
        return None
    if response.status_code != 200:
        print(f"Authentication failed: {_server_error(response)}")
        return None

    try:
        body = response.json()
        expires_in = body.get("expires_in")
        if expires_in:
            print(f"Logged in. Session expires after {expires_in // 60} min idle.")
        return body["token"]
    except (requests.exceptions.JSONDecodeError, KeyError):
        print("Invalid response from server")
        return None


def logout():
    """Revoke the current token so it cannot be reused."""
    if not token:
        return
    try:
        requests.post(f"{SERVER_URL}/logout", headers=auth_headers(), timeout=10)
    except requests.exceptions.RequestException:
        # Best effort: the token still expires on its own.
        pass


def choose_room():
    """Select a chat room on start. Send and see messages from this room."""
    rooms_ids = []
    try:
        response = requests.get(
            f"{SERVER_URL}/rooms", headers=auth_headers(), timeout=10
        )
        response.raise_for_status()

        for i, room in enumerate(response.json()):
            rooms_ids.append(room["id"])
            print(f"{i + 1}. {room['topic']}")
    except requests.exceptions.HTTPError as e:
        print(f"Could not list rooms: {_server_error(e.response)}")
        return None
    except (requests.exceptions.RequestException, KeyError):
        print("Invalid response from server")
        return None

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
        # The server derives the sender from the connection's token; username is
        # sent only for backwards compatibility and is ignored.
        data = {"message": new_message, "room_id": room}
        sio.emit("message", data)


def main():
    global username
    global room
    global token
    try:
        username = get_username()
        token = authenticate(username)
        if not token:
            return
        room = choose_room()
        if room is None:
            return

        sio.connect(SERVER_URL, auth={"token": token})
        input_thread = threading.Thread(target=send_messages)
        input_thread.daemon = True
        input_thread.start()

        sio_thread = threading.Thread(target=sio.wait)
        sio_thread.start()

        input_thread.join()
        sio_thread.join()
    except socketio.exceptions.ConnectionError:
        print("Could not connect: authentication rejected or server unavailable.")
    except (KeyboardInterrupt, EOFError):
        # Ctrl-C / Ctrl-D at one of the prompts.
        sio.disconnect()
    finally:
        logout()


if __name__ == "__main__":
    main()
