# Асинхронный сервис процессинга платежей

Микросервис принимает платежи по HTTP, кладёт событие в outbox, публикует его в RabbitMQ и асинхронно обрабатывает через внешний шлюз (эмуляция). Результат уходит клиенту webhook-ом.

Документация:

- [HTTP API](docs/API.md) — эндпоинты, заголовки, ошибки, webhook
- [Архитектура](docs/ARCHITECTURE.md) — outbox, consumer, retry, DLQ
- [Тесты](docs/TESTING.md) — покрытие и запуск

## Архитектура

```mermaid
sequenceDiagram
    participant Client
    participant API
    participant DB
    participant Outbox as Outbox publisher
    participant MQ as RabbitMQ
    participant Worker as Consumer
    participant Gateway as Payment gateway (emulation)
    participant Hook as Webhook URL

    Client->>API: POST /api/v1/payments
    API->>DB: INSERT payment + outbox (одна транзакция)
    API-->>Client: 202 Accepted
    Outbox->>DB: SELECT unpublished FOR UPDATE SKIP LOCKED
    Outbox->>MQ: publish payments.new
    MQ->>Worker: consume payments.new
    Worker->>Gateway: 2–5 сек, 90% success
    Worker->>DB: UPDATE status
    Worker->>Hook: POST result (retry 3 раза)
```

Гарантии доставки:

- **Outbox** — событие пишется в БД вместе с платежом, публикация в брокер идёт отдельным циклом.
- **Idempotency-Key** — повтор с тем же ключом и телом возвращает тот же платёж; другое тело даёт `409`.
- **Retry** — до 3 попыток обработки сообщения с экспоненциальной задержкой 2с / 4с (очереди `payments.retry.1/2`).
- **DLQ** — после 3 неудач сообщение уходит в `payments.new.dlq`.
- Webhook отдельно ретраится 3 раза (`1с`, `2с`) внутри попытки обработки.

## Стек

FastAPI, Pydantic v2, SQLAlchemy 2.0 (async), PostgreSQL, RabbitMQ + FastStream, Alembic, Docker Compose.

## Запуск

```bash
docker compose up --build
```

Сервисы:

| Сервис     | URL                          |
|------------|------------------------------|
| API        | http://localhost:8000        |
| Swagger    | http://localhost:8000/docs   |
| RabbitMQ UI| http://localhost:15672       |
| PostgreSQL | localhost:5432               |

Учётка RabbitMQ: `guest` / `guest`.  
API-ключ по умолчанию: `dev-api-key` (переменная `API_KEY`).

Остановка:

```bash
docker compose down
```

## Переменные окружения

| Переменная                   | По умолчанию                                                         | Назначение              |
|------------------------------|----------------------------------------------------------------------|-------------------------|
| `API_KEY`                    | `dev-api-key`                                                        | Значение `X-API-Key`    |
| `DATABASE_URL`               | `postgresql+asyncpg://postgres:postgres@localhost:5432/payments`     | PostgreSQL              |
| `RABBITMQ_URL`               | `amqp://guest:guest@localhost:5672/`                                 | RabbitMQ                |
| `OUTBOX_POLL_INTERVAL_SEC`   | `0.5`                                                                | Период опроса outbox    |
| `LOG_LEVEL`                  | `INFO`                                                               | Уровень логов           |
| `WEBHOOK_TIMEOUT_SEC`        | `10`                                                                 | Таймаут HTTP webhook    |

Пример: `.env.example`.

## Тесты

```bash
docker compose --profile test run --rm tests
```

Либо локально на Python 3.12: `pip install -r requirements-dev.txt && pytest -q`.

Подробности: [docs/TESTING.md](docs/TESTING.md).

## Примеры API

Создание платежа:

```bash
curl -s -X POST http://localhost:8000/api/v1/payments \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-api-key" \
  -H "Idempotency-Key: order-1001" \
  -d '{
    "amount": "199.90",
    "currency": "RUB",
    "description": "Order 1001",
    "metadata": {"order_id": "1001"},
    "webhook_url": "http://api:8000/webhook-sink"
  }'
```

Ответ `202 Accepted`:

```json
{
  "payment_id": "8b1c3d2e-2f4a-4b6c-9d0e-1a2b3c4d5e6f",
  "status": "pending",
  "created_at": "2026-10-14T12:00:00.000000+00:00"
}
```

Получение платежа (через 2–5 секунд статус станет `succeeded` или `failed`):

```bash
curl -s http://localhost:8000/api/v1/payments/<payment_id> \
  -H "X-API-Key: dev-api-key"
```

`webhook_url` `http://api:8000/webhook-sink` — демо-приёмник внутри compose, результат пишется в логи сервиса `api`. С хоста можно указать любой публичный URL, например webhook.site.

Повтор с тем же `Idempotency-Key` и тем же телом вернёт исходный `payment_id` без дубля. Другое тело с тем же ключом — `409 Conflict`. Без `X-API-Key` — `401`.

## Очереди RabbitMQ

| Объект                 | Назначение                                      |
|------------------------|-------------------------------------------------|
| exchange `payments`    | Публикация новых платежей                       |
| queue `payments.new`   | Основная очередь consumer                       |
| `payments.retry.1/2`   | TTL-очереди экспоненциального retry             |
| exchange `payments.dlx`| Dead letter exchange                            |
| queue `payments.new.dlq` | Сообщения после 3 неудачных попыток           |

## Локальный запуск без Docker

Нужны PostgreSQL и RabbitMQ, затем:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
python -m app.consumer
```

## Структура

```
app/
  api/v1/          # HTTP эндпоинты
  broker/          # FastStream, топология RabbitMQ, consumer handler
  models/          # payments, outbox
  schemas/         # Pydantic v2
  services/        # создание платежа, шлюз, webhook, обработка
  workers/outbox.py
  main.py          # FastAPI + outbox publisher
  consumer.py      # FastStream worker
alembic/versions/  # миграции
docs/              # API, архитектура, тесты
tests/             # pytest
```
