import uuid
from pydantic import BaseModel
from datetime import datetime


class ConversationCreateResponse(BaseModel):
    conversation_id: uuid.UUID
    title: str


class ConversationListItem(BaseModel):
    conversation_id: uuid.UUID
    title: str
    updated_at: datetime


class MessageItem(BaseModel):
    role: str
    content: str
    created_at: datetime
