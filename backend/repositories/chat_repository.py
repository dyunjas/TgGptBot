from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from aiogram.types import User as TgUser
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import Chat, ChatMessage, MessageRole, User, UserChatState, utc_now


@dataclass(slots=True)
class PaginatedResult:
    items: list
    total: int
    page: int
    page_size: int

    @property
    def total_pages(self) -> int:
        if self.total <= 0:
            return 1
        return (self.total + self.page_size - 1) // self.page_size


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
            )
            self._session.add(user)
            await self._session.flush()
            return user

        user.username = tg_user.username
        user.first_name = tg_user.first_name
        user.last_name = tg_user.last_name
        user.language_code = tg_user.language_code
        await self._session.flush()
        return user

    async def get_user_by_telegram_id(self, telegram_user_id: int) -> Optional[User]:
        result = await self._session.execute(
            select(User).where(User.telegram_id == telegram_user_id).limit(1)
        )
        return result.scalar_one_or_none()

    async def _ensure_user_chat_state(self, user_id: int) -> UserChatState:
        result = await self._session.execute(
            select(UserChatState).where(UserChatState.user_id == user_id).limit(1)
        )
        state = result.scalar_one_or_none()
        if state is None:
            state = UserChatState(user_id=user_id, active_chat_id=None)
            self._session.add(state)
            await self._session.flush()
        return state

    async def _next_internal_chat_key(self, user_id: int) -> int:
        result = await self._session.execute(
            select(func.max(Chat.telegram_chat_id)).where(Chat.user_id == user_id)
        )
        max_key = result.scalar_one_or_none() or 0
        return int(max_key) + 1

    async def create_chat(
        self,
        *,
        user_id: int,
        title: Optional[str] = None,
        set_active: bool = True,
    ) -> Chat:
        internal_key = await self._next_internal_chat_key(user_id)
        chat_title = title.strip() if title and title.strip() else f"Чат {internal_key}"
        chat = Chat(
            user_id=user_id,
            telegram_chat_id=internal_key,
            title=chat_title,
        )
        self._session.add(chat)
        await self._session.flush()

        if set_active:
            await self.set_active_chat(user_id=user_id, chat_id=chat.id)

        return chat

    async def set_active_chat(self, *, user_id: int, chat_id: Optional[int]) -> UserChatState:
        state = await self._ensure_user_chat_state(user_id)
        state.active_chat_id = chat_id
        state.updated_at = utc_now()
        await self._session.flush()
        return state

    async def get_active_chat_for_user(self, user_id: int) -> Optional[Chat]:
        result = await self._session.execute(
            select(UserChatState).where(UserChatState.user_id == user_id).limit(1)
        )
        state = result.scalar_one_or_none()
        if state is None or state.active_chat_id is None:
            return None

        result = await self._session.execute(
            select(Chat)
            .where(Chat.id == state.active_chat_id, Chat.user_id == user_id)
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_chat_by_id_for_user(self, *, user_id: int, chat_id: int) -> Optional[Chat]:
        result = await self._session.execute(
            select(Chat)
            .where(Chat.id == chat_id, Chat.user_id == user_id)
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_or_create_active_chat(self, *, user_id: int) -> Chat:
        chat = await self.get_active_chat_for_user(user_id=user_id)
        if chat is not None:
            return chat
        return await self.create_chat(user_id=user_id, set_active=True)

    async def list_user_chats(
        self,
        *,
        user_id: int,
        page: int,
        page_size: int,
    ) -> PaginatedResult:
        current_page = max(1, page)
        size = max(1, page_size)

        total_stmt = select(func.count(Chat.id)).where(Chat.user_id == user_id)
        total = int((await self._session.execute(total_stmt)).scalar_one() or 0)

        stmt: Select[tuple[Chat]] = (
            select(Chat)
            .where(Chat.user_id == user_id)
            .order_by(Chat.updated_at.desc(), Chat.id.desc())
            .offset((current_page - 1) * size)
            .limit(size)
        )
        result = await self._session.execute(stmt)
        chats = list(result.scalars().all())
        return PaginatedResult(items=chats, total=total, page=current_page, page_size=size)

    async def get_chat_messages_page(
        self,
        *,
        chat_id: int,
        page: int,
        page_size: int,
    ) -> PaginatedResult:
        current_page = max(1, page)
        size = max(1, page_size)

        total_stmt = select(func.count(ChatMessage.id)).where(ChatMessage.chat_id == chat_id)
        total = int((await self._session.execute(total_stmt)).scalar_one() or 0)

        stmt: Select[tuple[ChatMessage]] = (
            select(ChatMessage)
            .where(ChatMessage.chat_id == chat_id)
            .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
            .offset((current_page - 1) * size)
            .limit(size)
        )
        result = await self._session.execute(stmt)
        messages = list(result.scalars().all())
        messages.reverse()
        return PaginatedResult(items=messages, total=total, page=current_page, page_size=size)

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
            .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        messages = list(result.scalars().all())
        messages.reverse()
        return messages
