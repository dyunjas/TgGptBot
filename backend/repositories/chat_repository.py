from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Optional

from aiogram.types import Chat as TgChat
from aiogram.types import User as TgUser
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.database.models import Chat, ChatMessage, MessageRole, User, utc_now


@dataclass(slots=True)
class UserChatsWithMessages:
    user: User
    chats: list[Chat]


class ChatRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_or_create_user_from_telegram(self, tg_user: TgUser) -> User:
        result = await self._session.execute(
            select(User).where(User.telegram_id == tg_user.id).limit(1)
        )
        user = result.scalar_one_or_none()
        if user is None:
            user = User(
                telegram_id=tg_user.id,
                username=tg_user.username,
                first_name=tg_user.first_name,
                last_name=tg_user.last_name,
                language_code=tg_user.language_code,
                is_bot=tg_user.is_bot,
            )
            self._session.add(user)
            await self._session.flush()
            return user

        user.username = tg_user.username
        user.first_name = tg_user.first_name
        user.last_name = tg_user.last_name
        user.language_code = tg_user.language_code
        user.is_bot = tg_user.is_bot
        await self._session.flush()
        return user

    async def get_or_create_chat_for_user(self, user_id: int, tg_chat: TgChat) -> Chat:
        result = await self._session.execute(
            select(Chat)
            .where(Chat.user_id == user_id, Chat.telegram_chat_id == tg_chat.id)
            .limit(1)
        )
        chat = result.scalar_one_or_none()
        if chat is None:
            chat = Chat(
                user_id=user_id,
                telegram_chat_id=tg_chat.id,
                title=tg_chat.title,
            )
            self._session.add(chat)
            await self._session.flush()
            return chat

        chat.title = tg_chat.title
        await self._session.flush()
        return chat

    async def save_message(
        self,
        *,
        user_id: int,
        chat_id: int,
        role: MessageRole,
        content: str,
        model_name: Optional[str] = None,
    ) -> ChatMessage:
        message = ChatMessage(
            user_id=user_id,
            chat_id=chat_id,
            role=role,
            content=content,
            model_name=model_name,
        )
        self._session.add(message)
        chat = await self._session.get(Chat, chat_id)
        if chat is not None:
            chat.updated_at = utc_now()
        await self._session.flush()
        return message

    async def get_recent_chat_history(self, chat_id: int, limit: int = 20) -> list[ChatMessage]:
        stmt: Select[tuple[ChatMessage]] = (
            select(ChatMessage)
            .where(ChatMessage.chat_id == chat_id)
            .order_by(ChatMessage.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        messages = list(result.scalars().all())
        messages.reverse()
        return messages

    async def get_user_chats_with_messages(
        self,
        *,
        telegram_user_id: int,
        per_chat_limit: int = 10,
    ) -> Optional[UserChatsWithMessages]:
        result = await self._session.execute(
            select(User).where(User.telegram_id == telegram_user_id).limit(1)
        )
        user = result.scalar_one_or_none()
        if user is None:
            return None

        chats_result = await self._session.execute(
            select(Chat)
            .options(selectinload(Chat.messages))
            .where(Chat.user_id == user.id)
            .order_by(Chat.updated_at.desc())
        )
        chats: Sequence[Chat] = chats_result.scalars().all()
        for chat in chats:
            if per_chat_limit > 0 and len(chat.messages) > per_chat_limit:
                chat.messages = chat.messages[-per_chat_limit:]

        return UserChatsWithMessages(user=user, chats=list(chats))
