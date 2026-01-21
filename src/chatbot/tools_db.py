from sqlmodel.ext.asyncio.session import AsyncSession
from langchain_openai import ChatOpenAI

from src.chatbot.service import MSSQLConnector



class DBTool:
    
    @staticmethod
    async def stream_answer(
        conn: MSSQLConnector,
        llm: ChatOpenAI,
        session: AsyncSession,
        question: str
    ):

        # ✅ run your SQL-RAG pipeline (streaming tokens)
        async for token in conn.invoke_streaming(question, llm, session):
            yield token
