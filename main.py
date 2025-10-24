from mssql_agent.sqldb import MSSQLConnector
from fastapi import FastAPI, HTTPException,Request
from fastapi.responses import StreamingResponse
from mssql_agent.sqldb import MSSQLConnector
from langchain_openai import ChatOpenAI
import json
import asyncio


app = FastAPI(title="SQL LLM API")


llm= ChatOpenAI(
        openai_api_key="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",
        openai_api_base="https://openrouter.ai/api/v1",
        model="meta-llama/llama-3.3-70b-instruct"
        )

conn = MSSQLConnector(
    username="sa",
    password="sa@12309876",
    host="192.168.152.22",
    port=1433,
    database="SONA-MESX0-QA-TEST-SAP"
)

# #Postgres - readonly access
# conn = MSSQLConnector(
#     username="readonly_user",
#     password="Hari571",
#     host="localhost",
#     port=3005,
#     database="CT_Demo"
# )
   
@app.post("/query_stream")
async def run_query_stream(req: Request):
    data = await req.json()
    question = data.get("question")
    if not question:
        raise HTTPException(status_code=400, detail="Missing 'question'")

    async def stream_response():
        async for token in conn.invoke_streaming(question, llm):
            # Yield each token as JSON line
            yield json.dumps({"chunk": token}) + "\n"

    return StreamingResponse(stream_response(), media_type="text/plain")