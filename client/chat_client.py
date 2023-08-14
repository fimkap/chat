import asyncio
import requests
import aioconsole
import os


async def get_messages(room_id):
    while True:
        os.system("clear")  # clear the terminal on update

        try:
            response = requests.get(f"http://localhost/rooms/{room_id}/messages")
            response.raise_for_status()

            for item in response.json():
                print(f"{item['sender_id']}: {item['message']}")
        except (requests.exceptions.JSONDecodeError, KeyError) as e:
            print(f"Invalid response from server: {e}")

        print("New Message:")
        await asyncio.sleep(3)


async def send_messages(room_id, username):
    while True:
        new_message = await aioconsole.ainput("")
        data = {"sender_id": username, "message": new_message}

        try:
            response = requests.post(f"http://localhost/rooms/{room_id}/messages", json=data)
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            print(f"Error sending message: {e}")

        await asyncio.sleep(1)


def choose_room():
    """Select a chat room on start. Send and see messages from this room."""
    rooms_ids = []
    try:
        response = requests.get("http://localhost/rooms")
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


def join_room(room_id, username):
    try:
        response = requests.post(f"http://localhost/rooms/{room_id}/users/{username}")
        response.raise_for_status()
    except requests.exceptions.HTTPError:
        print("Invalid response from server")


async def main():
    username = input("Enter your username: ")
    if not username or len(username) < 3 or len(username) > 20:
        print("Username must be between 3 and 20 characters")
        return
    room_id = choose_room()
    join_room(room_id, username)

    tasks = [
        asyncio.create_task(get_messages(room_id)),
        asyncio.create_task(send_messages(room_id, username)),
    ]

    await asyncio.gather(*tasks)


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
