import logging
from sqlmodel.ext.asyncio.session import AsyncSession
from langchain_openai import ChatOpenAI

from src.chatbot.service import MSSQLConnector

logger = logging.getLogger(__name__)


class DBTool:
    @staticmethod
    async def stream_answer(
        conn: MSSQLConnector,
        llm: ChatOpenAI,
        session: AsyncSession,
        conversation_id,
        question: str,
        request_id: str = "-",
    ):
        """
        Streams answer from DB tool (SQL-RAG pipeline).
        """

        logger.info(
            f"[DB_TOOL_START] conversation_id={conversation_id} question={question[:120]}",
            extra={"request_id": request_id},
        )

        try:
            # ✅ run SQL-RAG pipeline (streaming tokens)
            async for token in conn.invoke_streaming(
                question=question,
                llm=llm,
                session=session,
                request_id=request_id,   # ✅ CRITICAL for DB logs
            ):
                yield token

            logger.info(
                f"[DB_TOOL_END] conversation_id={conversation_id}",
                extra={"request_id": request_id},
            )

        except Exception as e:
            logger.exception(
                f"[DB_TOOL_ERROR] conversation_id={conversation_id} error={str(e)}",
                extra={"request_id": request_id},
            )
            raise
