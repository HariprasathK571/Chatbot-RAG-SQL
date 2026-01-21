from typing_extensions import TypedDict, Literal
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate


class RouteOutput(TypedDict):
    route: Literal["general", "db"]
    reason: str


class AgentRouter:
    @staticmethod
    async def pick_route(question: str, llm: ChatOpenAI) -> str:
        prompt = ChatPromptTemplate.from_messages([
            ("system",
             "You are a routing agent for a Banking SQL chatbot.\n\n"
             "Decide if the user's question requires database access.\n\n"
             "Return ONLY JSON with:\n"
             '{{ "route": "general" | "db", "reason": "short reason" }}\n\n'
             "Use route=db when the user asks for:\n"
             "- balances, account info, transaction list\n"
             "- counts, totals, branch KPIs\n"
             "- customers, loans, outstanding, repayments\n"
             "- top N / last N / highest / lowest\n"
             "- anything that requires actual DB values\n\n"
             "Use route=general when the user asks:\n"
             "- definitions, explanations, greetings\n"
             "- how the system works\n"
             "- coding help unrelated to actual database records\n"),
            ("user", "Question: {q}")
        ])

        structured = llm.with_structured_output(RouteOutput)
        res = await structured.ainvoke(prompt.format_messages(q=question))

        return res.get("route", "general")
