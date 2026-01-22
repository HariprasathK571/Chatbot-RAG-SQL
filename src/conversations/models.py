import uuid
from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, ForeignKey
from sqlalchemy.dialects.postgresql import UUID


class Conversation(SQLModel, table=True):
    __tablename__ = "conversations"

    conversation_id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True)
    user_id: int = Field(index=True)

    title: Optional[str] = Field(default="New Chat", max_length=200)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# class Message(SQLModel, table=True):
#     __tablename__ = "messages"

#     message_id: Optional[int] = Field(default=None, primary_key=True)

#     conversation_id: uuid.UUID = Field(index=True, foreign_key="conversations.conversation_id")

#     role: str = Field(max_length=20)  # user/assistant/system
#     content: str

#     created_at: datetime = Field(default_factory=datetime.utcnow)

class Message(SQLModel, table=True):
    __tablename__ = "messages"

    message_id: Optional[int] = Field(default=None, primary_key=True)

    conversation_id: uuid.UUID = Field(
        sa_column=Column(
            UUID(as_uuid=True),
            ForeignKey("conversations.conversation_id", ondelete="CASCADE"),  # ✅ correct
            nullable=False,
            index=True,
        )
    )

    role: str = Field(max_length=20)
    content: str

    created_at: datetime = Field(default_factory=datetime.utcnow)