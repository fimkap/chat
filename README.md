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

To use the chat:

Run the backend:

docker-compose up -d

Run the client as many times as needed (not wrapped in a Docker container):

python chat_client.py

The client will prompt for a username, allow you to choose a chat room, and start chatting. Simply enter your text and press Enter. An empty message will result in an error.

The client will download the chat room's history (in a real system, this would likely be limited).

