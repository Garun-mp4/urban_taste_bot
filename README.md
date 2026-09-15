# Urban Taste AI Telegram CRM

Полноценный Telegram-бот для ресторана Urban Taste: отвечает на вопросы клиентов через OpenAI API, сохраняет историю диалогов, принимает заявки на бронирование и передаёт обращения администратору.

## Возможности

- приветствие и меню действий по `/start`;
- ответы AI только на основе базы знаний Urban Taste;
- автоматическая передача вопросов, на которые нет ответа в базе знаний, администратору;
- пошаговое бронирование: имя, количество гостей, дата, время и телефон;
- сохранение пользователей, заявок и истории сообщений в PostgreSQL;
- Redis-хранилище состояний диалога;
- команды администратора `/stats` и `/new_requests`;
- изменение статуса заявки кнопками: `NEW`, `IN_PROGRESS`, `DONE`;
- Docker Compose для запуска всех сервисов.

## Технологии

- Python 3.12;
- aiogram 3;
- OpenAI API через официальный Python SDK;
- PostgreSQL 16;
- Redis 7;
- SQLAlchemy 2 с asyncpg;
- Docker Compose.

## Запуск

### 1. Клонирование проекта

```bash
git clone <URL_РЕПОЗИТОРИЯ>
cd Urban_taste_bot
```

### 2. Создание `.env`

Linux/macOS:

```bash
cp .env.example .env
```

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Файл `.env` добавлен в `.gitignore` и не должен попадать в Git.

### 3. Заполнение переменных

Откройте `.env` и укажите реальные значения:

```dotenv
TELEGRAM_BOT_TOKEN=<YOUR_BOT_TOKEN>
ADMIN_CHAT_ID=<YOUR_CHAT_ID>
OPENAI_API_KEY=<YOUR_OPENAI_API_KEY>
OPENAI_MODEL=gpt-5.6-luna
OPENAI_REASONING_EFFORT=medium
```

Для запуска через Docker Compose оставьте подключение к сервисам Docker:

```dotenv
POSTGRES_DB=urban_taste
POSTGRES_USER=urban_taste
POSTGRES_PASSWORD=change_me
DATABASE_URL=postgresql+asyncpg://urban_taste:change_me@db:5432/urban_taste
REDIS_URL=redis://redis:6379/0
```

По умолчанию бот использует `gpt-5.6-luna` с `medium` reasoning. `OPENAI_MODEL` и `OPENAI_REASONING_EFFORT` можно изменить под доступную в вашем OpenAI API модель. Подписка ChatGPT для работы бота не используется.

### 4. Запуск

```bash
docker compose up -d
```

Compose поднимет PostgreSQL и Redis, дождётся их healthcheck, после чего запустит бота. При изменении исходников пересоберите образ:

```bash
docker compose up -d --build
```

### 5. Проверка

```bash
docker compose ps
docker compose logs -f bot
```

После появления сообщения о запуске найдите бота в Telegram и отправьте `/start`. Администратору отправьте `/stats` или `/new_requests` в чате, ID которого указан в `ADMIN_CHAT_ID`.

## Структура проекта

```text
app/
├── ai/
│   ├── openai_client.py    # OpenAI API и разбор структурированного ответа
│   └── prompts.py          # база знаний и правила ассистента
├── bot/
│   ├── handlers/           # клиентские, booking и admin handlers
│   ├── keyboards/          # reply и inline клавиатуры
│   ├── middlewares/        # транзакционная DB-сессия и user context
│   └── utils.py
├── database/
│   ├── database.py         # engine, pool, инициализация схемы
│   └── models.py           # users, conversation_messages, client_requests
├── services/               # пользователи, диалоги, заявки, уведомления, валидация
├── config.py
└── main.py
```

Схема PostgreSQL создаётся при первом запуске на основе SQLAlchemy metadata. Перед изменением моделей в рабочей среде следует подключить версионируемые миграции Alembic.

## Администратор и безопасность

- Доступ к `/stats`, `/new_requests` и кнопкам изменения статуса разрешён только в чате из `ADMIN_CHAT_ID`.
- Секреты хранятся в `.env`; реальные ключи и токены нельзя добавлять в исходники, README или коммиты.
- Бот не сообщает клиенту непроверенные цены, наличие или условия. Неизвестные вопросы создают заявку типа `question`.
- Telegram-токен, опубликованный где-либо вне защищённого хранилища, следует перевыпустить через BotFather.

## Остановка

```bash
docker compose down
```

Команда останавливает контейнеры, но сохраняет данные в Docker volumes. Не используйте `docker compose down -v`, если нужно сохранить базу данных.
