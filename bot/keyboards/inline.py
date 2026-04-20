from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from backend.database.models import Chat
from backend.repositories import PaginatedResult


def main_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Новый чат", callback_data="menu:new_chat")
    builder.button(text="Мои чаты", callback_data="menu:my_chats:1")
    builder.button(text="Помощь", callback_data="menu:help")
    builder.adjust(1, 1, 1)
    return builder.as_markup()


def chats_keyboard(
    *,
    chats_page: PaginatedResult,
    active_chat_id: int | None,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    for chat in chats_page.items:
        assert isinstance(chat, Chat)
        title = chat.title or f"Чат {chat.telegram_chat_id}"
        marker = "[*]" if chat.id == active_chat_id else "[ ]"
        builder.button(
            text=f"{marker} {title[:28]}",
            callback_data=f"chat:open:{chat.id}:1",
        )

    prev_page = max(1, chats_page.page - 1)
    next_page = min(chats_page.total_pages, chats_page.page + 1)
    builder.button(text="<", callback_data=f"menu:my_chats:{prev_page}")
    builder.button(text=f"{chats_page.page}/{chats_page.total_pages}", callback_data="menu:noop")
    builder.button(text=">", callback_data=f"menu:my_chats:{next_page}")

    builder.button(text="Новый чат", callback_data="menu:new_chat")
    builder.button(text="Обновить", callback_data=f"menu:my_chats:{chats_page.page}")
    builder.button(text="Главное меню", callback_data="menu:main")
    builder.adjust(1, 3, 1, 1, 1)
    return builder.as_markup()


def chat_messages_keyboard(
    *,
    chat_id: int,
    page: int,
    total_pages: int,
    is_active: bool,
    chats_page: int = 1,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    prev_page = max(1, page - 1)
    next_page = min(total_pages, page + 1)

    builder.button(text="<", callback_data=f"chat:open:{chat_id}:{prev_page}")
    builder.button(text=f"{page}/{total_pages}", callback_data="menu:noop")
    builder.button(text=">", callback_data=f"chat:open:{chat_id}:{next_page}")

    if is_active:
        builder.button(text="Активный чат", callback_data="menu:noop")
    else:
        builder.button(text="Сделать активным", callback_data=f"chat:activate:{chat_id}:{page}")

    builder.button(text="К списку чатов", callback_data=f"menu:my_chats:{chats_page}")
    builder.button(text="Новый чат", callback_data="menu:new_chat")
    builder.adjust(3, 1, 1, 1)
    return builder.as_markup()
