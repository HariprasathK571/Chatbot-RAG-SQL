from mssql_agent.sqldb import MSSQLConnector
from langchain_openai import ChatOpenAI

llm= ChatOpenAI(
        openai_api_key="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",
        openai_api_base="https://openrouter.ai/api/v1",
        model="meta-llama/llama-3.3-70b-instruct:free"
        )


conn = MSSQLConnector(
    username="sa",
    password="sa@12309876",
    host="192.168.152.22",
    port=1433,
    database="commonality"
)


# conn.invoke("how many different lots are available?",llm)