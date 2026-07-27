#Milestone 1 - Chat Server REST API
1. Implement a simple chat server with the following REST API: a. Send Message - user sends request with username and message
 b. Get Messages - user retrieves a list of all previous messages
2. No need to support multiple “chats rooms”
3. Wrap the server with a simple Docker file.


#Milestone 2 - Chat Server Client
1. Implement a simple CLI textual client which:
 a. Requires a username for connection
 b. Prints all messages and updates it constantly.
 c. Prompts client to send a message
2. The client will poll the server periodically (every second) for all messages and display
3. Allow multiple clients to run simultaneously and connect to the server to chat.
4. Note: doesn’t have to look too pretty - just implement the required functionality.


#Milestone 3 - Store Messages in DB
1. Server side:
 a. Add to server logic that stores all messages in a database of your choosing.
 b. The database should be set up as a separate docker container.
 c. On server restart, clients should still receive the list of all previous messages.
 d. We expect the server to remember all messages if it restarted.


#Milestone 4 - Allow for Chat Rooms
1. Client side:
 a. On connection, allow the client to choose which room to connect to.
 b. Clients will see only messages sent to this room.
2. Server side:
 a. Change the API to support multiple rooms.


#Milestone 5 - Push Notification
1. Client side:
 a. Removing polling code from client.
 b. Clients should set up a persistent connection to the server.
 c. Clients will get a message as a push notification from the server over persistent
2. Server side:
 a. Implement persistent connection.
 b. When one client sends a message, send push notification to all other clients in the same room.

## Using the chat

### 1. Start the backend

```bash
docker compose up -d --build
```

The server listens on `http://localhost:5002` directly, and on
`http://localhost` (port 80) through nginx. Redis and its data volume come up
with it.

### 2. Set up a Python env for the client

The client is **not** wrapped in a Docker container, so it needs its own Python
environment. It requires two packages — `python-socketio[client]` and
`requests` — listed in `requirements-client.txt`. Without them you get
`ModuleNotFoundError: No module named 'socketio'`.

From the repo root (Python 3.10+):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-client.txt
```

Notes:

- On Debian/Ubuntu, `python3 -m venv` needs the `python3-venv` system package
  (`sudo apt install python3-venv`). If you'd rather not install it,
  [`uv`](https://docs.astral.sh/uv/) works without root:
  `uv venv .venv && VIRTUAL_ENV=.venv uv pip install -r requirements-client.txt`.
- `requirements.txt` is the **server's** dependency list (what the Docker image
  installs) — it does not include the client's.
- Working on the server itself? `pip install -r requirements-dev.txt` gets
  everything: server, client, pytest and ruff.

### 3. Run the client

With the env activated:

```bash
python client/chat_client.py      # from the repo root
# or:  cd client && python chat_client.py
```

If you skipped activating the env, call its interpreter directly:
`.venv/bin/python client/chat_client.py`.

Run it as many times as you like (separate terminals) to chat between users.

The client talks to `http://localhost:5002` by default. Point it elsewhere —
e.g. through nginx, or at another host — with `CHAT_SERVER_URL`:

```bash
CHAT_SERVER_URL=http://localhost python client/chat_client.py
```

The client will prompt for a username, allow you to choose a chat room, and start chatting. Simply enter your text and press Enter. An empty message will result in an error. Ctrl-C or Ctrl-D leaves the room and exits.

The client will download the chat room's history (in a real system, this would likely be limited).

https://github.com/fimkap/chat/assets/2026502/6de58d98-c517-4708-bdc8-d37b5ce34e94

