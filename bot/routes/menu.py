from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message

from backend.database.session import async_session
from backend.repositories import ChatRepository
from bot.formatters import format_chats_page
from bot.keyboards import chats_keyboard, main_menu_keyboard
from bot.texts import (
    CHAT_CREATED_TEXT,
    EMPTY_CHATS_TEXT,
    HELP_TEXT,
    START_TEXT,
)

router = Router(name="menu-router")

CHAT_LIST_PAGE_SIZE = 6


def _safe_positive_int(value: str, default: int = 1) -> int:
    try:
        parsed = int(value)
        if parsed > 0:
            return parsed
    except (TypeError, ValueError):
        pass
    return default


async def _send_or_edit(
    *,
    message: Message,
    text: str,
    reply_markup,
    edit: bool,
) -> None:
    if edit:
        try:
            await message.edit_text(text, reply_markup=reply_markup)
            return
        except Exception:
            pass
    await message.answer(text, reply_markup=reply_markup)


async def _render_user_chats(
    *,
    message: Message,
    telegram_user_id: int,
    page: int,
    edit: bool = False,
) -> None:
    async with async_session() as session:
        repo = ChatRepository(session)
        user = await repo.get_user_by_telegram_id(telegram_user_id)
        if user is None:
            await _send_or_edit(
                message=message,
                text=EMPTY_CHATS_TEXT,
                reply_markup=main_menu_keyboard(),
                edit=edit,
            )
            return

        chats_page = await repo.list_user_chats(
            user_id=user.id,
            page=page,
            page_size=CHAT_LIST_PAGE_SIZE,
        )
        active_chat = await repo.get_active_chat_for_user(user.id)

    if not chats_page.items:
        await _send_or_edit(
            message=message,
            text=EMPTY_CHATS_TEXT,
            reply_markup=main_menu_keyboard(),
            edit=edit,
        )
        return

    text = format_chats_page(
        chats_page=chats_page,
        active_chat_id=active_chat.id if active_chat else None,
    )
    keyboard = chats_keyboard(
        chats_page=chats_page,
        active_chat_id=active_chat.id if active_chat else None,
    )
    await _send_or_edit(message=message, text=text, reply_markup=keyboard, edit=edit)


async def _create_chat_and_notify(message: Message) -> None:
    if not message.from_user:
        return

    async with async_session() as session:
        repo = ChatRepository(session)
        db_user = await repo.get_or_create_user_from_telegram(message.from_user)
        new_chat = await repo.create_chat(user_id=db_user.id, set_active=True)
        await session.commit()

    await message.answer(
        CHAT_CREATED_TEXT.format(
            title=new_chat.title,
            chat_id=new_chat.id,
        ),
        reply_markup=main_menu_keyboard(),
    )


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(START_TEXT, reply_markup=main_menu_keyboard())


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(HELP_TEXT, reply_markup=main_menu_keyboard())


@router.message(Command("my_chats"))
async def cmd_my_chats(message: Message) -> None:
    if not message.from_user:
        return
    await _render_user_chats(
        message=message,
        telegram_user_id=message.from_user.id,
        page=1,
        edit=False,
    )


@router.message(Command("new_chat"))
async def cmd_new_chat(message: Message) -> None:
    await _create_chat_and_notify(message)


@router.callback_query(F.data == "menu:main")
async def callback_main_menu(callback: CallbackQuery) -> None:
    await callback.answer()
    if callback.message is None:
        return
    await callback.message.answer(START_TEXT, reply_markup=main_menu_keyboard())


@router.callback_query(F.data == "menu:help")
async def callback_help(callback: CallbackQuery) -> None:
    await callback.answer()
    if callback.message is None:
        return
    await callback.message.answer(HELP_TEXT, reply_markup=main_menu_keyboard())


@router.callback_query(F.data == "menu:new_chat")
async def callback_new_chat(callback: CallbackQuery) -> None:
    await callback.answer()
    if callback.message is None or callback.from_user is None:
        return

    async with async_session() as session:
        repo = ChatRepository(session)
        db_user = await repo.get_or_create_user_from_telegram(callback.from_user)
        new_chat = await repo.create_chat(user_id=db_user.id, set_active=True)
        await session.commit()

    await callback.message.answer(
        CHAT_CREATED_TEXT.format(title=new_chat.title, chat_id=new_chat.id),
        reply_markup=main_menu_keyboard(),
    )


@router.callback_query(F.data.startswith("menu:my_chats"))
async def callback_my_chats(callback: CallbackQuery) -> None:
    await callback.answer()
    if callback.message is None or callback.from_user is None:
        return

    parts = (callback.data or "").split(":")
    page = 1
    if len(parts) >= 3:
        page = _safe_positive_int(parts[2], default=1)

    await _render_user_chats(
        message=callback.message,
        telegram_user_id=callback.from_user.id,
        page=page,
        edit=True,
    )


@router.callback_query(F.data == "menu:noop")
async def callback_noop(callback: CallbackQuery) -> None:
    await callback.answer()
