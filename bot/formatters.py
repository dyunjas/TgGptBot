from __future__ import annotations

from backend.database.models import Chat, ChatMessage, MessageRole
from backend.repositories import PaginatedResult


ROLE_LABELS = {
    MessageRole.USER: "Вы",
    MessageRole.ASSISTANT: "Бот",
    MessageRole.SYSTEM: "Система",
}


def _trim_text(value: str, *, limit: int = 120) -> str:
    text = value.strip().replace("\n", " ")
    if len(text) <= limit:
        return text
    return f"{text[:limit].rstrip()}..."


def format_chats_page(
    *,
    chats_page: PaginatedResult,
    active_chat_id: int | None,
) -> str:
    lines = ["<b>Ваши чаты</b>"]
    lines.append(f"Страница {chats_page.page}/{chats_page.total_pages}")

    if not chats_page.items:
        lines.append("\nЧатов пока нет. Нажмите «Новый чат».")
        return "\n".join(lines)

    for chat in chats_page.items:
        assert isinstance(chat, Chat)
        marker = "[*]" if chat.id == active_chat_id else "[ ]"
        title = _trim_text(chat.title or f"Чат {chat.telegram_chat_id}", limit=40)
        lines.append(f"{marker} <b>{title}</b>  <code>#{chat.id}</code>")

    lines.append("\nИспользуйте кнопки чатов ниже, чтобы открыть историю.")
    return "\n".join(lines)


def format_chat_messages_page(
    *,
    chat: Chat,
    messages_page: PaginatedResult,
    is_active: bool,
) -> str:
    status = "активный" if is_active else "неактивный"
    lines = [
        f"<b>{chat.title or f'Чат {chat.telegram_chat_id}'}</b>",
        f"Чат <code>#{chat.id}</code> | {status}",
        f"Сообщения: страница {messages_page.page}/{messages_page.total_pages}",
    ]

    if not messages_page.items:
        lines.append("\nСообщений пока нет. Отправьте текст, чтобы начать диалог.")
        return "\n".join(lines)

    lines.append("")
    for msg in messages_page.items:
        assert isinstance(msg, ChatMessage)
        role = ROLE_LABELS.get(msg.role, "Участник")
        lines.append(f"<b>{role}:</b> {_trim_text(msg.content, limit=500)}")

    return "\n".join(lines)
