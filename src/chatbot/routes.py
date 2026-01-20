from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from langchain_openai import ChatOpenAI
from sqlmodel.ext.asyncio.session import AsyncSession
import json

from src.db.core import get_session
from src.chatbot.schema import ChatbotuserQuery
from src.chatbot.service import MSSQLConnector, rewrite_question_with_history

from src.auth.deps import get_current_user
from src.auth.models import User

from src.conversations.service import ConversationService, ConversationTitleGenerator


conn = MSSQLConnector()
chatbot_router = APIRouter()

llm= ChatOpenAI(
        openai_api_key="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",
        openai_api_base="https://openrouter.ai/api/v1",
        model="openai/gpt-4o-mini"
        )


@chatbot_router.post("/query_stream")
async def run_query_stream(
    req: ChatbotuserQuery,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    if not req.question or not req.question.strip():
        raise HTTPException(status_code=400, detail="Missing 'question'")

    question = req.question.strip()

    # ✅ validate conversation belongs to user
    convo = await ConversationService.get_conversation(session, req.conversation_id, current_user.user_id)
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    # ✅ last 5Q+5A
    history_window = await ConversationService.fetch_history_window(session, req.conversation_id)

    # ✅ rewrite question
    rewritten_question = await rewrite_question_with_history(llm, question, history_window)

    print(rewritten_question)

    # ✅ store user msg
    await ConversationService.add_message(session, req.conversation_id, "user", rewritten_question)

    # ✅ title generation on first msg
    msgs = await ConversationService.get_messages(session, req.conversation_id)
    if len(msgs) == 1 and (convo.title is None or convo.title.strip() == "New Chat"):
        title = await ConversationTitleGenerator.generate_title(question, llm)
        await ConversationService.update_conversation_title(session, convo, title)

    async def stream_response():
        assistant_answer = ""
        async for token in conn.invoke_streaming(rewritten_question, llm, session):
            assistant_answer += token
            yield json.dumps({"chunk": token}) + "\n"

        await ConversationService.add_message(session, req.conversation_id, "assistant", assistant_answer)
        await ConversationService.touch_conversation(session, convo)

    return StreamingResponse(stream_response(), media_type="text/plain")
