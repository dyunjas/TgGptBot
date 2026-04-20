# Telegram AI Bot

Телеграм-бот с поддержкой:
- нескольких чатов на пользователя;
- пагинации списка чатов и истории сообщений;
- отправки текста и изображений в AI;
- интеграции с Timeweb Cloud AI Agent (DeepSeek и другие модели агента).

## Требования

- Python 3.11+
- PostgreSQL

## Установка

```bash
git clone https://github.com/dyunjas/TgGptBot.git
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Настройка `.env`

Создайте/заполните файл `.env` в корне проекта:

```env
BOT_TOKEN=telegram_bot_token

POSTGRES_HOST=postgres_host
POSTGRES_PORT=postgres_port
POSTGRES_USER=postgres_user
POSTGRES_PASSWORD=postgres_password
POSTGRES_DB=postgres_db

TIMEWEB_API_KEY=timeweb_api_token
TIMEWEB_AGENT_ACCESS_ID=agent_access_id
TIMEWEB_BASE_URL=https://agent.timeweb.cloud
TIMEWEB_PROXY_SOURCE=telegram-bot
TIMEWEB_MODEL=deepseek-chat
TIMEWEB_SYSTEM_PROMPT=You are a helpful assistant. Answer briefly and clearly.
```

Где взять параметры Timeweb:
- `TIMEWEB_AGENT_ACCESS_ID`: в карточке агента, поле **Access ID**.
- `TIMEWEB_API_KEY`: в карточке агента, раздел **Токены авторизации** (создайте токен).
- `TIMEWEB_BASE_URL`: `https://agent.timeweb.cloud`.

## Запуск

```bash
python main.py
```

## Основные команды в Telegram

- `/start` — главное меню
- `/new_chat` — создать новый чат
- `/my_chats` — список чатов
- `/help` — помощь

## Примечания

- Таблицы БД создаются автоматически при запуске.
- История сообщений хранится по отдельным чатам пользователя.
