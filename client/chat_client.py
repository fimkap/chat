import asyncio
import requests
import aioconsole
import os


async def get_messages(username):
    room_id = 1
    while True:
        os.system("clear")  # clear the terminal on update

        try:
            response = requests.get(f"http://localhost/rooms/{room_id}/messages")
            response.raise_for_status()

            for item in response.json():
                print(f"{item['sender_id']}: {item['message']}")
        except (requests.exceptions.JSONDecodeError, KeyError):
            print("Invalid response from server")

        print("New Message:")
        await asyncio.sleep(3)


async def send_messages(username):
    while True:
        new_message = await aioconsole.ainput("")
        data = {"sender_id": username, "message": new_message}

        try:
            response = requests.post("http://localhost/rooms/1/messages", json=data)
            response.raise_for_status()
        except requests.exceptions.HTTPError:
            print("Invalid response from server")

        await asyncio.sleep(1)


async def main():
    username = input("Enter your username: ")

    tasks = [
        asyncio.create_task(get_messages(username)),
        asyncio.create_task(send_messages(username)),
    ]

    await asyncio.gather(*tasks)


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
