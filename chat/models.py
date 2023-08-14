from pydantic import BaseModel, Field

MAX_MESSAGE_LEN = 144
MIN_SENDER_LEN = 3
MAX_SENDER_LEN = 16
MIN_TOPIC_LEN = 3
MAX_TOPIC_LEN = 24


class User(BaseModel):
    name: str = Field(
        min_length=MIN_SENDER_LEN, max_length=MAX_SENDER_LEN, pattern=r"^[a-zA-Z0-9_-]+$"
    )


class Message(BaseModel):
    sender_id: str
    timestamp: float
    message: str = Field(min_length=1, max_length=MAX_MESSAGE_LEN)


class ChatRoom(BaseModel):
    id: int
    topic: str = Field(
        min_length=MIN_TOPIC_LEN, max_length=MAX_TOPIC_LEN, pattern=r"^[a-zA-Z0-9_]+$"
    )
