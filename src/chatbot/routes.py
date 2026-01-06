from fastapi import APIRouter,HTTPException,Request,Depends
from fastapi.responses import StreamingResponse
from langchain_openai import ChatOpenAI
from sqlmodel.ext.asyncio.session import AsyncSession
import json
from .service import MSSQLConnector
from src.db.core import get_session

conn = MSSQLConnector()

chatbot_router = APIRouter()

llm= ChatOpenAI(
        openai_api_key="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",
        openai_api_base="https://openrouter.ai/api/v1",
        model="openai/gpt-4o-mini"
        )

@chatbot_router.post("/query_stream")
async def run_query_stream(req: Request,session: AsyncSession = Depends(get_session)):
    data = await req.json()
    question = data.get("question")
    if not question:
        raise HTTPException(status_code=400, detail="Missing 'question'")

    async def stream_response():
        async for token in conn.invoke_streaming(question, llm,session):
            # Yield each token as JSON line
            yield json.dumps({"chunk": token}) + "\n"

    return StreamingResponse(stream_response(), media_type="text/plain")