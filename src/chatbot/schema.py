from pydantic import BaseModel

class ChatbotuserQuery(BaseModel):
    question: str