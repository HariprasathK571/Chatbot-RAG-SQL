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
    database="CT_Demo"
)


    
@app.post("/query_stream")
async def run_query_stream(req: Request):
    data = await req.json()
    question = data.get("question")
    if not question:
        raise HTTPException(status_code=400, detail="Missing 'question'")

    async def event_generator():
        queue = asyncio.Queue()

        # callback to receive tokens from MSSQLConnector
        def token_callback(token: str):
            asyncio.create_task(queue.put(token))

        # Start streaming
        asyncio.create_task(conn.invoke_streaming(question, llm, token_callback))

        while True:
            token = await queue.get()
            if token is None:  # end of stream
                break
            # yield json.dumps({"chunk": token}) + "\n"
            text_piece = token.content if hasattr(token, "content") else str(token)
            yield json.dumps({"chunk": text_piece}) + "\n"

    return StreamingResponse(event_generator(), media_type="application/json")