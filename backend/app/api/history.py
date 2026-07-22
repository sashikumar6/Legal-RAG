"""Chat history search — auth required, strictly scoped to the caller's own conversations."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user_required
from app.database import crud, get_async_session
from app.database.models import User

router = APIRouter(prefix="/history", tags=["history"])


class HistoryResultItem(BaseModel):
    conversation_id: str
    title: Optional[str] = None
    mode: Optional[str] = None
    updated_at: str


class HistorySearchResponse(BaseModel):
    query: str
    results: list[HistoryResultItem]


class ConversationListResponse(BaseModel):
    results: list[HistoryResultItem]
    next_offset: Optional[int] = None


class HistoryMessageItem(BaseModel):
    role: str
    content: str
    mode: Optional[str] = None
    confidence: Optional[str] = None
    citations: list = []
    created_at: str


class ConversationDetailResponse(BaseModel):
    conversation_id: str
    title: Optional[str] = None
    mode: Optional[str] = None
    messages: list[HistoryMessageItem]


@router.get("/search", response_model=HistorySearchResponse)
async def search_history(
    q: str = Query(..., min_length=1),
    limit: int = Query(20, le=50),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_async_session),
):
    conversations = await crud.search_conversations(db, user.id, q, limit=limit, offset=offset)
    return HistorySearchResponse(
        query=q,
        results=[
            HistoryResultItem(
                conversation_id=str(c.id),
                title=c.title,
                mode=c.mode,
                updated_at=(c.updated_at or c.created_at).isoformat(),
            )
            for c in conversations
        ],
    )


@router.get("/conversations", response_model=ConversationListResponse)
async def list_history(
    limit: int = Query(30, ge=1, le=50),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_async_session),
):
    conversations = await crud.list_conversations(db, user.id, limit=limit + 1, offset=offset)
    has_more = len(conversations) > limit
    visible = conversations[:limit]
    return ConversationListResponse(
        results=[
            HistoryResultItem(
                conversation_id=str(c.id),
                title=c.title,
                mode=c.mode,
                updated_at=(c.updated_at or c.created_at).isoformat(),
            )
            for c in visible
        ],
        next_offset=offset + limit if has_more else None,
    )


@router.get("/conversations/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation(
    conversation_id: str,
    user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_async_session),
):
    result = await crud.get_owned_conversation_with_messages(db, user.id, conversation_id)
    if result is None:
        raise HTTPException(404, "Conversation not found")

    conversation, messages = result
    return ConversationDetailResponse(
        conversation_id=str(conversation.id),
        title=conversation.title,
        mode=conversation.mode,
        messages=[
            HistoryMessageItem(
                role=m.role,
                content=m.content,
                mode=m.mode,
                confidence=m.confidence,
                citations=m.citations or [],
                created_at=m.created_at.isoformat(),
            )
            for m in messages
        ],
    )
