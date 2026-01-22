from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse
from sqlmodel.ext.asyncio.session import AsyncSession
from langchain_openai import ChatOpenAI
import json
import time
import logging

from src.db.core import get_session
from src.auth.deps import get_current_user
from src.auth.models import User

from src.chatbot.schema import ChatbotuserQuery
from src.chatbot.service import MSSQLConnector, rewrite_question_with_history

from src.chatbot.agent_router import AgentRouter
from src.chatbot.tools_general import GeneralTool
from src.chatbot.tools_db import DBTool

from src.conversations.service import ConversationService, ConversationTitleGenerator
import os
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

chatbot_router = APIRouter()
conn = MSSQLConnector()

load_dotenv()  # loads .env variables

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_API_BASE = os.getenv("OPENAI_API_BASE", "https://openrouter.ai/api/v1")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "openai/gpt-4o-mini")

if not OPENAI_API_KEY:
    raise RuntimeError("Missing OPENAI_API_KEY in environment variables")

# ✅ LLM Config (OpenRouter)
llm = ChatOpenAI(
    openai_api_key=OPENAI_API_KEY,
    openai_api_base=OPENAI_API_BASE,
    model=OPENAI_MODEL,
)


@chatbot_router.post("/query_stream")
async def run_query_stream(
    req: ChatbotuserQuery,
    request: Request,  # ✅ REQUIRED for request_id
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    start = time.perf_counter()
    rid = getattr(request.state, "request_id", "-")

    # ---------------------------
    # ✅ Validate question
    # ---------------------------
    question = (req.question or "").strip()
    if not question:
        logger.warning(
            f"[CHATBOT_EMPTY_QUESTION] user_id={current_user.user_id}",
            extra={"request_id": rid},
        )
        raise HTTPException(status_code=400, detail="Missing 'question'")

    logger.info(
        f"[CHATBOT_REQUEST_RECEIVED] user_id={current_user.user_id} conversation_id={req.conversation_id} q={question[:120]}",
        extra={"request_id": rid},
    )

    # ---------------------------
    # ✅ Validate conversation belongs to user
    # ---------------------------
    convo = await ConversationService.get_conversation(session, req.conversation_id, current_user.user_id)
    if not convo:
        logger.warning(
            f"[CHATBOT_CONVERSATION_NOT_FOUND] user_id={current_user.user_id} conversation_id={req.conversation_id}",
            extra={"request_id": rid},
        )
        raise HTTPException(status_code=404, detail="Conversation not found")

    # ---------------------------
    # ✅ Fetch last 5Q+5A
    # ---------------------------
    history_window = await ConversationService.fetch_history_window(session, req.conversation_id)
    logger.info(
        f"[CHATBOT_HISTORY_FETCHED] conversation_id={req.conversation_id} history_messages={len(history_window)}",
        extra={"request_id": rid},
    )

    # ---------------------------
    # ✅ Rewrite question based on history
    # ---------------------------
    rewritten_question = await rewrite_question_with_history(
        llm=llm,
        current_question=question,
        history=history_window,
        request_id=rid,
    )

    logger.info(
        f"[CHATBOT_REWRITE_DONE] conversation_id={req.conversation_id} rewritten={rewritten_question[:120]}",
        extra={"request_id": rid},
    )

    # ---------------------------
    # ✅ Save user msg
    # ---------------------------
    await ConversationService.add_message(session, req.conversation_id, "user", rewritten_question)
    logger.info(
        f"[CHATBOT_USER_MESSAGE_SAVED] conversation_id={req.conversation_id}",
        extra={"request_id": rid},
    )

    # ---------------------------
    # ✅ Generate title only for first message
    # ---------------------------
    msgs = await ConversationService.get_messages(session, req.conversation_id)
    if len(msgs) == 1 and (convo.title is None or convo.title.strip() == "New Chat"):
        try:
            title = await ConversationTitleGenerator.generate_title(question, llm)
            await ConversationService.update_conversation_title(session, convo, title)

            logger.info(
                f"[CHATBOT_TITLE_GENERATED] conversation_id={req.conversation_id} title={title}",
                extra={"request_id": rid},
            )
        except Exception as e:
            logger.warning(
                f"[CHATBOT_TITLE_FAILED] conversation_id={req.conversation_id} error={str(e)}",
                extra={"request_id": rid},
            )

    # ---------------------------
    # ✅ Decide routing (db or general)
    # ---------------------------
    route = await AgentRouter.pick_route(rewritten_question, llm)
    logger.info(
        f"[CHATBOT_ROUTE_DECISION] conversation_id={req.conversation_id} route={route}",
        extra={"request_id": rid},
    )

    # ---------------------------
    # ✅ Streaming generator
    # ---------------------------
    async def stream_response():
        assistant_answer = ""
        stream_start = time.perf_counter()

        try:
            logger.info(
                f"[CHATBOT_STREAM_START] conversation_id={req.conversation_id} route={route}",
                extra={"request_id": rid},
            )

            # ✅ Tool: GENERAL
            if route == "general":
                logger.info(
                    f"[TOOL_GENERAL_START] conversation_id={req.conversation_id}",
                    extra={"request_id": rid},
                )

                async for token in GeneralTool.stream_answer(llm, rewritten_question, request_id=rid):
                    assistant_answer += token
                    yield json.dumps({"chunk": token, "route": "general"}) + "\n"

                logger.info(
                    f"[TOOL_GENERAL_END] conversation_id={req.conversation_id} assistant_chars={len(assistant_answer)}",
                    extra={"request_id": rid},
                )

            # ✅ Tool: DB
            else:
                logger.info(
                    f"[TOOL_DB_START] conversation_id={req.conversation_id}",
                    extra={"request_id": rid},
                )

                async for token in DBTool.stream_answer(
                    conn=conn,
                    llm=llm,
                    session=session,
                    conversation_id=req.conversation_id,
                    question=rewritten_question,
                    request_id=rid,  # ✅ IMPORTANT: pass request_id into DB tool
                ):
                    assistant_answer += token
                    yield json.dumps({"chunk": token, "route": "db"}) + "\n"

                logger.info(
                    f"[TOOL_DB_END] conversation_id={req.conversation_id} assistant_chars={len(assistant_answer)}",
                    extra={"request_id": rid},
                )

        except Exception as e:
            logger.exception(
                f"[CHATBOT_STREAM_ERROR] conversation_id={req.conversation_id} route={route} error={str(e)}",
                extra={"request_id": rid},
            )
            yield json.dumps({"chunk": "\nSorry, something went wrong.\n", "route": route}) + "\n"

        finally:
            # ✅ always attempt save assistant reply
            try:
                await ConversationService.add_message(session, req.conversation_id, "assistant", assistant_answer)
                logger.info(
                    f"[CHATBOT_ASSISTANT_MESSAGE_SAVED] conversation_id={req.conversation_id}",
                    extra={"request_id": rid},
                )
            except Exception as e:
                logger.exception(
                    f"[CHATBOT_ASSISTANT_SAVE_FAILED] conversation_id={req.conversation_id} error={str(e)}",
                    extra={"request_id": rid},
                )

            # ✅ always update updated_at
            try:
                await ConversationService.touch_conversation(session, convo)
            except Exception:
                pass

            stream_elapsed = (time.perf_counter() - stream_start) * 1000
            total_elapsed = (time.perf_counter() - start) * 1000

            logger.info(
                f"[CHATBOT_STREAM_END] conversation_id={req.conversation_id} route={route} "
                f"assistant_chars={len(assistant_answer)} stream_ms={stream_elapsed:.2f} total_ms={total_elapsed:.2f}",
                extra={"request_id": rid},
            )

    return StreamingResponse(stream_response(), media_type="text/plain")
