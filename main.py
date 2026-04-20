import asyncio

from bot import close_chat_service, router as chat_router
from backend.core.loader import setup_bot, shutdown_bot
from backend.core.logger_config import logger
from backend.database.session import check_connection, init_db


async def main() -> None:
    bot, dp = await setup_bot()

    is_connected = await check_connection()
    if not is_connected:
        logger.error("Cannot start bot because database is disconnected")
        await shutdown_bot(bot)
        return

    await init_db()
    dp.include_router(chat_router)

    try:
        await dp.start_polling(bot)
    finally:
        await close_chat_service()
        await shutdown_bot(bot)


if __name__ == "__main__":
    asyncio.run(main())
