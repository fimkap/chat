import asyncio
import requests
import aioconsole
import os
import socketio

sio = socketio.AsyncClient()

room = 0
username = ""


@sio.event
async def connect():
    global username
    global room
    username = get_username()
    room = choose_room()
    await sio.emit('join', {'username': username, 'room': room})


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


async def get_messages(room_id):
    while True:
        os.system("clear")  # clear the terminal on update

        try:
            response = requests.get(f"http://localhost:5002/rooms/{room_id}/messages")
            response.raise_for_status()

            for item in response.json():
                print(f"{item['sender_id']}: {item['message']}")
        except (requests.exceptions.JSONDecodeError, KeyError) as e:
            print(f"Invalid response from server: {e}")

        print("New Message:")
        await asyncio.sleep(3)


async def send_messages():
    """Send messages to the server. Input is taken from the console."""
    while True:
        new_message = await aioconsole.ainput("")
        print("\033[A \033[A")
        data = {"username": username, "message": new_message, "room_id": room}
        await sio.emit("message", data)

        await asyncio.sleep(1)


def choose_room():
    """Select a chat room on start. Send and see messages from this room."""
    rooms_ids = []
    try:
        response = requests.get("http://localhost:5002/rooms")
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


def get_username():
    username = input("Enter your username: ")
    if not username or len(username) < 3 or len(username) > 20:
        print("Username must be between 3 and 20 characters")
        return
    return username


async def main():

    # websocket connection
    await sio.connect("http://localhost:5002")

    tasks = [
        # asyncio.create_task(get_messages(room_id)),
        asyncio.create_task(send_messages()),
    ]

    await asyncio.gather(*tasks)
    await sio.wait()


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
