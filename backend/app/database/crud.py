"""Persistence helpers for chat history (sessions, conversations, messages, users).

Kept as a separate seam from `services/`: this module only does DB reads/writes,
callers decide how to handle failures (see ChatService.process_query, which wraps
all of this defensively so a DB outage never breaks the chat endpoint itself).
"""

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Conversation, Message, Session, User


def _parse_uuid(value: Optional[str]) -> Optional[uuid.UUID]:
    if not value:
        return None
    try:
        return uuid.UUID(value)
    except ValueError:
        return None


async def get_or_create_user_by_identity(db: AsyncSession, sub: str, email: Optional[str]) -> User:
    """Resolve the local User row for a verified external identity (Supabase's `sub` claim)."""
    result = await db.execute(select(User).where(User.external_id == sub))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(external_id=sub, email=email)
        db.add(user)
        await db.flush()
    elif email and user.email != email:
        user.email = email
    return user


async def get_or_create_session(
    db: AsyncSession, session_id: str, user_id: Optional[uuid.UUID] = None
) -> Session:
    """Resolve the app-level Session row for a client-generated session id.

    If the caller is now authenticated and the existing session was anonymous,
    attach it to the user (covers "logged in partway through a conversation").
    """
    sid = _parse_uuid(session_id) or uuid.uuid4()
    result = await db.execute(select(Session).where(Session.id == sid))
    session_row = result.scalar_one_or_none()
    if session_row is None:
        session_row = Session(id=sid, user_id=user_id)
        db.add(session_row)
        await db.flush()
    elif user_id is not None and session_row.user_id is None:
        session_row.user_id = user_id
    return session_row


async def get_or_create_conversation(
    db: AsyncSession,
    session_row: Session,
    conversation_id: Optional[str],
    seed_title: str,
    mode: Optional[str] = None,
    user_id: Optional[uuid.UUID] = None,
) -> Conversation:
    """Resolve a conversation, ownership-checked against the caller's session or account.

    A bare id lookup would let a stranger who obtains/guesses a conversation UUID
    append messages to someone else's conversation, so reuse only fires if the
    conversation belongs to this exact session, or (for logged-in users) to any
    session owned by the same account.
    """
    cid = _parse_uuid(conversation_id)
    if cid is not None:
        stmt = select(Conversation).join(Session, Conversation.session_id == Session.id).where(
            Conversation.id == cid
        )
        if user_id is not None:
            stmt = stmt.where(or_(Session.id == session_row.id, Session.user_id == user_id))
        else:
            stmt = stmt.where(Session.id == session_row.id)
        result = await db.execute(stmt)
        conversation = result.scalar_one_or_none()
        if conversation is not None:
            return conversation

    conversation = Conversation(
        session_id=session_row.id,
        title=seed_title[:500] if seed_title else None,
        mode=mode,
    )
    db.add(conversation)
    await db.flush()
    return conversation


async def add_message(
    db: AsyncSession,
    conversation_id: uuid.UUID,
    role: str,
    content: str,
    mode: Optional[str] = None,
    confidence: Optional[str] = None,
    citations: Optional[list] = None,
) -> Message:
    message = Message(
        conversation_id=conversation_id,
        role=role,
        content=content,
        mode=mode,
        confidence=confidence,
        citations=citations or [],
    )
    db.add(message)
    await db.flush()
    return message


async def search_conversations(
    db: AsyncSession, user_id: uuid.UUID, query: str, limit: int = 20, offset: int = 0
) -> list[Conversation]:
    """ILIKE search over the caller's own conversations — title or any message content.

    Simple substring search, not full-text search: adequate at per-user chat-history
    volume, avoids adding tsvector/trigram index infrastructure prematurely.
    """
    like = f"%{query}%"
    stmt = (
        select(Conversation)
        .join(Session, Conversation.session_id == Session.id)
        .where(Session.user_id == user_id)
        .where(
            or_(
                Conversation.title.ilike(like),
                Conversation.messages.any(Message.content.ilike(like)),
            )
        )
        .order_by(Conversation.updated_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    return list(result.scalars().unique().all())


async def list_conversations(
    db: AsyncSession, user_id: uuid.UUID, limit: int = 20, offset: int = 0
) -> list[Conversation]:
    """Return a user's conversations in most-recently-updated order."""
    stmt = (
        select(Conversation)
        .join(Session, Conversation.session_id == Session.id)
        .where(Session.user_id == user_id)
        .order_by(Conversation.updated_at.desc(), Conversation.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    return list(result.scalars().unique().all())


async def get_owned_conversation_with_messages(
    db: AsyncSession, user_id: uuid.UUID, conversation_id: str
) -> Optional[tuple[Conversation, list[Message]]]:
    cid = _parse_uuid(conversation_id)
    if cid is None:
        return None

    stmt = (
        select(Conversation)
        .join(Session, Conversation.session_id == Session.id)
        .where(Conversation.id == cid, Session.user_id == user_id)
    )
    result = await db.execute(stmt)
    conversation = result.scalar_one_or_none()
    if conversation is None:
        return None

    msg_result = await db.execute(
        select(Message).where(Message.conversation_id == cid).order_by(Message.created_at.asc())
    )
    return conversation, list(msg_result.scalars().all())
