from pydantic import BaseModel, Field
from typing import Annotated

MAX_MESSAGE_LEN = 144
MIN_SENDER_LEN = 3
MAX_SENDER_LEN = 16
MIN_TOPIC_LEN = 3
MAX_TOPIC_LEN = 24


class User(BaseModel):
    name: Annotated[
        str,
        Field(
            min_length=MIN_SENDER_LEN,
            max_length=MAX_SENDER_LEN,
            pattern=r"^[a-zA-Z0-9_-]+$",
            description="Username containing only alphanumeric characters, underscores, and hyphens"
        )
    ]


class Message(BaseModel):
    sender_id: str
    timestamp: float
    message: Annotated[
        str,
        Field(
            min_length=1,
            max_length=MAX_MESSAGE_LEN,
            description="Message content"
        )
    ]


class ChatRoom(BaseModel):
    id: int
    topic: Annotated[
        str,
        Field(
            min_length=MIN_TOPIC_LEN,
            max_length=MAX_TOPIC_LEN,
            pattern=r"^[a-zA-Z0-9_]+$",
            description="Room topic containing only alphanumeric characters and underscores"
        )
    ]
