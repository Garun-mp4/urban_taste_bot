# Urban Taste AI Telegram CRM

Полноценный Telegram-бот для ресторана Urban Taste: отвечает на вопросы клиентов через OpenAI API, сохраняет историю диалогов, принимает заявки на бронирование и передаёт обращения администратору.

## Возможности

- приветствие и меню действий по `/start`;
- ответы AI только на основе базы знаний Urban Taste;
- автоматическая передача вопросов, на которые нет ответа в базе знаний, администратору;
- пошаговое бронирование: имя, количество гостей, дата, время и телефон;
- календарь и свободные временные слоты с проверкой часов работы и общей вместимости;
- сохранение пользователей, заявок и истории сообщений в PostgreSQL;
- отмена клиентом своей активной заявки и уведомления об изменении статуса;
- Redis-хранилище состояний диалога;
- команды администратора `/stats`, `/new_requests`, `/requests` и `/request <ID>`;
- поиск и фильтрация заявок по статусу, имени, телефону или тексту обращения;
- журнал событий заявки: создание, смена статуса, отмена клиентом и ответы администратора;
- ответы администратора через надежную outbox-очередь с повторными попытками доставки;
- изменение статуса заявки кнопками: `NEW`, `IN_PROGRESS`, `DONE`, `REJECTED`, `CANCELLED`;
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
# Для админской группы: Telegram ID администраторов через запятую
ADMIN_USER_IDS=
OPENAI_API_KEY=<YOUR_OPENAI_API_KEY>
OPENAI_MODEL=gpt-5.6-luna
OPENAI_REASONING_EFFORT=medium
DROP_PENDING_UPDATES=false
RATE_LIMIT_SECONDS=1.0
NOTIFICATION_POLL_SECONDS=2.0
NOTIFICATION_MAX_ATTEMPTS=10
RESERVATION_CAPACITY=50
RESERVATION_MAX_GUESTS=50
RESERVATION_DURATION_MINUTES=90
RESERVATION_SLOT_INTERVAL_MINUTES=30
RESERVATION_MIN_ADVANCE_MINUTES=30
RESERVATION_MAX_DAYS=30
PROCESSED_EVENT_RETENTION_DAYS=30
AI_HISTORY_LIMIT=12
AI_HISTORY_CHAR_LIMIT=24000
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

Параметры `RESERVATION_*` задают операционные правила бронирования: суммарную
вместимость ресторана, максимальный размер группы, длительность визита, шаг
временных слотов, минимальное время до визита и горизонт бронирования. Перед
запуском укажите фактическую вместимость ресторана. `PROCESSED_EVENT_RETENTION_DAYS`
задаёт срок хранения ключей уже обработанных Telegram-событий для защиты от
повторной доставки.

`AI_HISTORY_LIMIT` ограничивает число сообщений в контексте, а
`AI_HISTORY_CHAR_LIMIT` — его максимальный размер в символах. Это не позволяет
длинной переписке бесконечно увеличивать запросы к модели.

### 4. Запуск

```bash
docker compose up -d
```

Compose поднимет PostgreSQL и Redis, дождётся их healthcheck, применит миграции Alembic и запустит бота. При изменении исходников пересоберите образ:

```bash
docker compose up -d --build
```

### 5. Проверка

```bash
docker compose ps
docker compose logs -f bot
```

После появления сообщения о запуске найдите бота в Telegram и отправьте `/start`. Администратору отправьте `/stats` или `/new_requests` в чате, ID которого указан в `ADMIN_CHAT_ID`.

Для работы с CRM доступны команды:

- `/requests` — последние 10 заявок;
- `/requests NEW` — заявки с выбранным статусом;
- `/requests Иван` — поиск по имени, телефону или тексту обращения;
- `/requests NEW Иван` — совместный фильтр по статусу и поиску;
- `/request 123` — подробности заявки и журнал событий по её ID.

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
│   ├── database.py         # engine и pool PostgreSQL
│   └── models.py           # users, conversation_messages, client_requests
├── services/               # пользователи, диалоги, заявки, слоты, уведомления
├── config.py
└── main.py
alembic/
└── versions/               # версионируемые миграции PostgreSQL
```

Схема PostgreSQL управляется версионируемыми миграциями Alembic. Docker entrypoint применяет их до запуска бота. Для локального запуска без Docker выполните `alembic upgrade head` после настройки `DATABASE_URL`.

## Администратор и безопасность

- Доступ к `/stats`, `/new_requests`, `/requests`, `/request` и кнопкам изменения статуса разрешён только в `ADMIN_CHAT_ID`; для админской группы дополнительно заполните `ADMIN_USER_IDS`.
- Секреты хранятся в `.env`; реальные ключи и токены нельзя добавлять в исходники, README или коммиты.
- Бот не сообщает клиенту непроверенные цены, наличие или условия. Неизвестные вопросы создают заявку типа `question`.
- Telegram-токен, опубликованный где-либо вне защищённого хранилища, следует перевыпустить через BotFather.

## Остановка

```bash
docker compose down
```

Команда останавливает контейнеры, но сохраняет данные в Docker volumes. Не используйте `docker compose down -v`, если нужно сохранить базу данных.
