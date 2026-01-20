import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession

from src.db.core import get_session
from src.auth.deps import get_current_user
from src.auth.models import User

from src.conversations.service import ConversationService
from src.conversations.schema import ConversationCreateResponse, ConversationListItem, MessageItem

router = APIRouter()


@router.post("", response_model=ConversationCreateResponse)
async def create_conversation(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    convo = await ConversationService.create_conversation(session, current_user.user_id)
    return {"conversation_id": convo.conversation_id, "title": convo.title}


@router.get("", response_model=list[ConversationListItem])
async def list_conversations(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    convos = await ConversationService.list_conversations(session, current_user.user_id)
    return [{"conversation_id": c.conversation_id, "title": c.title, "updated_at": c.updated_at} for c in convos]


@router.get("/{conversation_id}/messages", response_model=list[MessageItem])
async def get_messages(
    conversation_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    convo = await ConversationService.get_conversation(session, conversation_id, current_user.user_id)
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")

    msgs = await ConversationService.get_messages(session, conversation_id)
    return [{"role": m.role, "content": m.content, "created_at": m.created_at} for m in msgs]
