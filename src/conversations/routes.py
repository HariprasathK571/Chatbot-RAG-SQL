import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.core import get_session
from src.auth.deps import get_current_user
from src.auth.models import User

from src.conversations.service import ConversationService
from src.conversations.schema import ConversationCreateResponse, ConversationListItem, MessageItem

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("", response_model=ConversationCreateResponse)
async def create_conversation(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    logger.info(f"[CONVERSATION_CREATE] user_id={current_user.user_id} creating new conversation")

    convo = await ConversationService.create_conversation(session, current_user.user_id)

    logger.info(
        f"[CONVERSATION_CREATE_SUCCESS] user_id={current_user.user_id} conversation_id={convo.conversation_id} title={convo.title}"
    )

    return {"conversation_id": convo.conversation_id, "title": convo.title}


@router.get("", response_model=list[ConversationListItem])
async def list_conversations(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    logger.info(f"[CONVERSATION_LIST] user_id={current_user.user_id} fetching conversation list")

    convos = await ConversationService.list_conversations(session, current_user.user_id)

    logger.info(
        f"[CONVERSATION_LIST_SUCCESS] user_id={current_user.user_id} total_conversations={len(convos)}"
    )

    return [{"conversation_id": c.conversation_id, "title": c.title, "updated_at": c.updated_at} for c in convos]


@router.get("/{conversation_id}/messages", response_model=list[MessageItem])
async def get_messages(
    conversation_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    logger.info(
        f"[MESSAGE_LIST] user_id={current_user.user_id} conversation_id={conversation_id} fetching messages"
    )

    convo = await ConversationService.get_conversation(session, conversation_id, current_user.user_id)
    if not convo:
        logger.warning(
            f"[MESSAGE_LIST_NOT_FOUND] user_id={current_user.user_id} conversation_id={conversation_id}"
        )
        raise HTTPException(status_code=404, detail="Conversation not found")

    msgs = await ConversationService.get_messages(session, conversation_id)

    logger.info(
        f"[MESSAGE_LIST_SUCCESS] user_id={current_user.user_id} conversation_id={conversation_id} message_count={len(msgs)}"
    )

    return [{"role": m.role, "content": m.content, "created_at": m.created_at} for m in msgs]


@router.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    logger.info(
        f"[CONVERSATION_DELETE] user_id={current_user.user_id} conversation_id={conversation_id} deleting conversation"
    )

    deleted = await ConversationService.delete_conversation(
        session=session,
        conversation_id=conversation_id,
        user_id=current_user.user_id,
    )

    if not deleted:
        logger.warning(
            f"[CONVERSATION_DELETE_NOT_FOUND] user_id={current_user.user_id} conversation_id={conversation_id}"
        )
        raise HTTPException(status_code=404, detail="Conversation not found")

    logger.info(
        f"[CONVERSATION_DELETE_SUCCESS] user_id={current_user.user_id} conversation_id={conversation_id}"
    )

    return {"message": "Conversation deleted successfully", "conversation_id": str(conversation_id)}
