from fastapi import APIRouter,HTTPException,Request,Depends
from fastapi.responses import StreamingResponse
from langchain_openai import ChatOpenAI
# from sqlmodel.ext.asyncio.session import AsyncSession
import json
from .service import MSSQLConnector
from src.db.core import DbSession


conn = MSSQLConnector()

chatbot_router = APIRouter()

llm= ChatOpenAI(
        openai_api_key="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",
        openai_api_base="https://openrouter.ai/api/v1",
        model="meta-llama/llama-3.3-70b-instruct"
        )

@chatbot_router.post("/query_stream")
async def run_query_stream(req: Request,db: DbSession):
    data = await req.json()
    question = data.get("question")
    if not question:
        raise HTTPException(status_code=400, detail="Missing 'question'")

    async def stream_response():
        async for token in conn.invoke_streaming(question, llm,db):
            # Yield each token as JSON line
            yield json.dumps({"chunk": token}) + "\n"

    return StreamingResponse(stream_response(), media_type="text/plain")