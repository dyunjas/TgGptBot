from aiogram import Router

from bot.dependencies import close_chat_service
from bot.routes import chat_router, menu_router

router = Router(name="root-bot-router")
router.include_router(menu_router)
router.include_router(chat_router)

__all__ = ["router", "close_chat_service"]
