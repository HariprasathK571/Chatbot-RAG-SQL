from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
import logging
logger = logging.getLogger(__name__)

class GeneralTool:
    
    @staticmethod
    async def stream_answer(llm: ChatOpenAI, question: str, request_id: str = "-"):
        prompt = ChatPromptTemplate.from_messages([
            ("system",
             "You are a helpful assistant.\n"
             "Answer clearly and briefly.\n"
             "Do NOT generate SQL.\n"
             "If user asks for DB numbers/data, say it requires database query."),
            ("user", "{q}")
        ])

        msgs = prompt.format_messages(q=question)
        logger.info(f"[GENERAL_TOOL] answering question={question[:120]}", extra={"request_id": request_id})
        async for token in llm.astream(msgs):
            yield token.content


