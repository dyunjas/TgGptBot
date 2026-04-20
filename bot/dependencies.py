from backend.services import TimewebChatService

chat_service = TimewebChatService()


async def close_chat_service() -> None:
    await chat_service.close()
