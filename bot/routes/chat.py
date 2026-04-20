from __future__ import annotations

import base64
from typing import Any

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from backend.core.config import settings
from backend.core.logger_config import logger
from backend.database.models import MessageRole
from backend.database.session import async_session
from backend.repositories import ChatRepository
from backend.services.openai_chat import ChatProviderError
from bot.dependencies import chat_service
from bot.formatters import format_chat_messages_page
from bot.keyboards import chat_messages_keyboard
from bot.texts import (
    AI_ERROR_TEXT,
    IMAGE_DOWNLOAD_ERROR_TEXT,
    IMAGE_TOO_LARGE_TEXT,
    AI_PROVIDER_ACCESS_ERROR_TEXT,
    CHAT_NOT_FOUND_TEXT,
    CHAT_SELECTED_TEXT,
    EMPTY_TEXT_MESSAGE,
)

router = Router(name="chat-router")

CHAT_MESSAGES_PAGE_SIZE = 6
MAX_IMAGE_BYTES = 4 * 1024 * 1024


def _safe_positive_int(value: str, default: int = 1) -> int:
    try:
        parsed = int(value)
        if parsed > 0:
            return parsed
    except (TypeError, ValueError):
        pass
    return default


def _build_image_data_url(image_bytes: bytes) -> str:
    encoded = base64.b64encode(image_bytes).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


async def _generate_answer_for_message(
    message: Message,
    *,
    history,
    latest_user_content: str | list[dict[str, Any]] | None = None,
) -> str | None:
    try:
        return await chat_service.generate_reply(
            history=history,
            latest_user_content=latest_user_content,
        )
    except ChatProviderError as exc:
        logger.error(exc.log_message)
        if exc.code == "auth":
            await message.answer(AI_PROVIDER_ACCESS_ERROR_TEXT)
        else:
            await message.answer(exc.user_message)
        return None
    except Exception:
        logger.exception("Timeweb generation failed")
        await message.answer(AI_ERROR_TEXT)
        return None


async def _render_chat_messages(
    *,
    callback: CallbackQuery,
    chat_id: int,
    page: int,
) -> None:
    if callback.message is None or callback.from_user is None:
        return

    async with async_session() as session:
        repo = ChatRepository(session)
        db_user = await repo.get_or_create_user_from_telegram(callback.from_user)
        chat = await repo.get_chat_by_id_for_user(user_id=db_user.id, chat_id=chat_id)
        if chat is None:
            await callback.message.answer(CHAT_NOT_FOUND_TEXT)
            return

        active_chat = await repo.get_active_chat_for_user(db_user.id)
        messages_page = await repo.get_chat_messages_page(
            chat_id=chat.id,
            page=page,
            page_size=CHAT_MESSAGES_PAGE_SIZE,
        )

    text = format_chat_messages_page(
        chat=chat,
        messages_page=messages_page,
        is_active=bool(active_chat and active_chat.id == chat.id),
    )
    keyboard = chat_messages_keyboard(
        chat_id=chat.id,
        page=messages_page.page,
        total_pages=messages_page.total_pages,
        is_active=bool(active_chat and active_chat.id == chat.id),
    )

    try:
        await callback.message.edit_text(text, reply_markup=keyboard)
    except Exception:
        await callback.message.answer(text, reply_markup=keyboard)


@router.callback_query(F.data.startswith("chat:open:"))
async def callback_open_chat(callback: CallbackQuery) -> None:
    await callback.answer()
    parts = (callback.data or "").split(":")
    if len(parts) < 4:
        return
    chat_id = _safe_positive_int(parts[2], default=0)
    page = _safe_positive_int(parts[3], default=1)
    if chat_id <= 0:
        return

    await _render_chat_messages(callback=callback, chat_id=chat_id, page=page)


@router.callback_query(F.data.startswith("chat:activate:"))
async def callback_activate_chat(callback: CallbackQuery) -> None:
    await callback.answer()
    if callback.from_user is None:
        return

    parts = (callback.data or "").split(":")
    if len(parts) < 4:
        return

    chat_id = _safe_positive_int(parts[2], default=0)
    page = _safe_positive_int(parts[3], default=1)
    if chat_id <= 0:
        return

    async with async_session() as session:
        repo = ChatRepository(session)
        db_user = await repo.get_or_create_user_from_telegram(callback.from_user)
        chat = await repo.get_chat_by_id_for_user(user_id=db_user.id, chat_id=chat_id)
        if chat is None:
            if callback.message:
                await callback.message.answer(CHAT_NOT_FOUND_TEXT)
            return

        await repo.set_active_chat(user_id=db_user.id, chat_id=chat.id)
        await session.commit()

    if callback.message is not None:
        await callback.message.answer(
            CHAT_SELECTED_TEXT.format(title=chat.title, chat_id=chat.id)
        )

    await _render_chat_messages(callback=callback, chat_id=chat_id, page=page)


@router.message(F.text & ~F.text.startswith("/"))
async def chat_with_ai(message: Message) -> None:
    if not message.from_user or not message.text:
        return

    user_text = message.text.strip()
    if not user_text:
        await message.answer(EMPTY_TEXT_MESSAGE)
        return

    async with async_session() as session:
        repo = ChatRepository(session)
        db_user = await repo.get_or_create_user_from_telegram(message.from_user)
        active_chat = await repo.get_or_create_active_chat(user_id=db_user.id)
        await repo.save_message(
            user_id=db_user.id,
            chat_id=active_chat.id,
            role=MessageRole.USER,
            content=user_text,
        )
        history = await repo.get_recent_chat_history(chat_id=active_chat.id, limit=20)
        await session.commit()

    answer = await _generate_answer_for_message(
        message,
        history=history,
        latest_user_content=None,
    )
    if answer is None:
        return

    async with async_session() as session:
        repo = ChatRepository(session)
        db_user = await repo.get_or_create_user_from_telegram(message.from_user)
        active_chat = await repo.get_or_create_active_chat(user_id=db_user.id)
        await repo.save_message(
            user_id=db_user.id,
            chat_id=active_chat.id,
            role=MessageRole.ASSISTANT,
            content=answer,
            model_name=settings.TIMEWEB_MODEL,
        )
        await session.commit()

    await message.answer(answer)


@router.message(F.photo)
async def chat_with_ai_image(message: Message) -> None:
    if not message.from_user or not message.photo:
        return

    photo = message.photo[-1]
    caption = (message.caption or "").strip()
    text_part = caption if caption else "Опиши это изображение."

    try:
        file = await message.bot.get_file(photo.file_id)
        if not file.file_path:
            await message.answer(IMAGE_DOWNLOAD_ERROR_TEXT)
            return
        downloaded = await message.bot.download_file(file.file_path)
        image_bytes = downloaded.read()
    except Exception:
        logger.exception("Failed to download image from Telegram")
        await message.answer(IMAGE_DOWNLOAD_ERROR_TEXT)
        return

    if len(image_bytes) > MAX_IMAGE_BYTES:
        await message.answer(IMAGE_TOO_LARGE_TEXT)
        return

    latest_user_content: list[dict[str, Any]] = [
        {"type": "text", "text": text_part},
        {"type": "image_url", "image_url": {"url": _build_image_data_url(image_bytes)}},
    ]

    async with async_session() as session:
        repo = ChatRepository(session)
        db_user = await repo.get_or_create_user_from_telegram(message.from_user)
        active_chat = await repo.get_or_create_active_chat(user_id=db_user.id)
        history = await repo.get_recent_chat_history(chat_id=active_chat.id, limit=20)
        await session.commit()

    answer = await _generate_answer_for_message(
        message,
        history=history,
        latest_user_content=latest_user_content,
    )
    if answer is None:
        return

    caption_preview = caption if caption else "(без подписи)"
    user_log_text = f"[изображение] {caption_preview} | file_id={photo.file_id}"

    async with async_session() as session:
        repo = ChatRepository(session)
        db_user = await repo.get_or_create_user_from_telegram(message.from_user)
        active_chat = await repo.get_or_create_active_chat(user_id=db_user.id)
        await repo.save_message(
            user_id=db_user.id,
            chat_id=active_chat.id,
            role=MessageRole.USER,
            content=user_log_text,
        )
        await repo.save_message(
            user_id=db_user.id,
            chat_id=active_chat.id,
            role=MessageRole.ASSISTANT,
            content=answer,
            model_name=settings.TIMEWEB_MODEL,
        )
        await session.commit()

    await message.answer(answer)
