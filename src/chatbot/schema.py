from pydantic import BaseModel
import uuid

class ChatbotuserQuery(BaseModel):
    question: str
    conversation_id: uuid.UUID 