import uuid
from datetime import datetime
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy import desc

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from src.conversations.models import Conversation, Message


class ConversationTitleGenerator:
    @staticmethod
    async def generate_title(question: str, llm: ChatOpenAI) -> str:
        prompt = ChatPromptTemplate.from_messages([
            ("system",
             "Generate a short chat title.\n"
             "Rules:\n"
             "- Output ONLY the title\n"
             "- 2 to 6 words\n"
             "- No quotes\n"
             "- No trailing punctuation\n"
             "Examples: JWT Login Module, Chat Tabs Feature, SQL Query Fix"),
            ("user", "Create a title for this message:\n{question}")
        ])

        msgs = prompt.format_messages(question=question)
        resp = await llm.ainvoke(msgs)
        title = (resp.content or "").strip()
        title = title.replace('"', "").replace("'", "").strip()
        return title[:200] if title else "New Chat"


class ConversationService:
    MAX_WINDOW_MESSAGES = 10  # last 5Q + 5A

    @staticmethod
    async def create_conversation(session: AsyncSession, user_id: int) -> Conversation:
        convo = Conversation(user_id=user_id, title="New Chat")
        session.add(convo)
        await session.commit()
        await session.refresh(convo)
        return convo

    @staticmethod
    async def list_conversations(session: AsyncSession, user_id: int, limit: int = 30):
        stmt = (
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(desc(Conversation.updated_at))
            .limit(limit)
        )
        result = await session.exec(stmt)
        return result.all()

    @staticmethod
    async def get_conversation(session: AsyncSession, conversation_id: uuid.UUID, user_id: int):
        stmt = (
            select(Conversation)
            .where(Conversation.conversation_id == conversation_id)
            .where(Conversation.user_id == user_id)
        )
        result = await session.exec(stmt)
        return result.one_or_none()

    @staticmethod
    async def get_messages(session: AsyncSession, conversation_id: uuid.UUID):
        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
        )
        result = await session.exec(stmt)
        return result.all()

    @staticmethod
    async def add_message(session: AsyncSession, conversation_id: uuid.UUID, role: str, content: str):
        msg = Message(conversation_id=conversation_id, role=role, content=content)
        session.add(msg)
        await session.commit()
        await session.refresh(msg)
        return msg

    @staticmethod
    async def fetch_history_window(session: AsyncSession, conversation_id: uuid.UUID):
        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(desc(Message.created_at))
            .limit(ConversationService.MAX_WINDOW_MESSAGES)
        )
        result = await session.exec(stmt)
        rows = result.all()
        rows = list(reversed(rows))
        return [{"role": r.role, "content": r.content} for r in rows]

    @staticmethod
    async def touch_conversation(session: AsyncSession, convo: Conversation):
        convo.updated_at = datetime.utcnow()
        session.add(convo)
        await session.commit()

    @staticmethod
    async def update_conversation_title(session: AsyncSession, convo: Conversation, title: str):
        convo.title = (title or "New Chat")[:200]
        await ConversationService.touch_conversation(session, convo)
