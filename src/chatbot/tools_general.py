from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate


class GeneralTool:
    
    @staticmethod
    async def stream_answer(llm: ChatOpenAI, question: str):
        prompt = ChatPromptTemplate.from_messages([
            ("system",
             "You are a helpful assistant.\n"
             "Answer clearly and briefly.\n"
             "Do NOT generate SQL.\n"
             "If user asks for DB numbers/data, say it requires database query."),
            ("user", "{q}")
        ])

        msgs = prompt.format_messages(q=question)

        async for token in llm.astream(msgs):
            yield token.content
