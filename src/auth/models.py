from sqlmodel import SQLModel, Field
from datetime import datetime
from typing import Optional


class User(SQLModel, table=True):
    __tablename__ = "users"

    user_id: Optional[int] = Field(default=None, primary_key=True)

    full_name: str
    email: str = Field(index=True, unique=True)
    hashed_password: str

    is_active: bool = Field(default=True)
    role: str = Field(default="user")  # admin/user

    created_at: datetime = Field(default_factory=datetime.utcnow)
