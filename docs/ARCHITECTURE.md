# Архитектура

Сервис разделён на API-процесс и consumer-процесс. Они делят PostgreSQL и RabbitMQ, но не вызывают друг друга по HTTP.

```
Клиент ──POST──► API ──INSERT──► PostgreSQL (payments + outbox)
                    │
                    └── outbox publisher ──publish──► RabbitMQ payments.new
                                                         │
Consumer ◄───────────────────────────────────────────────┘
   │  эмуляция шлюза 2–5с, 90% success
   ├── UPDATE payments.status
   └── POST webhook_url (retry)
```

## Компоненты

| Процесс   | Код                    | Роль                                              |
|-----------|------------------------|---------------------------------------------------|
| API       | `app/main.py`          | HTTP, создание платежа, фоновый outbox publisher  |
| Consumer  | `app/consumer.py`      | Один FastStream handler на очередь `payments.new` |
| PostgreSQL| таблицы `payments`, `outbox` | Источник истины по платежу и неотправленным событиям |
| RabbitMQ  | exchange `payments`    | Доставка `payments.new`, retry TTL, DLQ           |

## Outbox

`POST /payments` в одной транзакции:

1. Вставляет `payments` со статусом `pending`.
2. Вставляет `outbox` с `payload = {payment_id, event_type}` и `published_at = NULL`.

Отдельный цикл (`app/workers/outbox.py`) каждые `OUTBOX_POLL_INTERVAL_SEC`:

- `SELECT … FOR UPDATE SKIP LOCKED` неопубликованных строк;
- `publish` в exchange `payments`, routing key `payments.new`;
- ставит `published_at`.

Если брокер недоступен, строка остаётся unpublished и уйдёт в следующей итерации. Так событие не теряется, даже если процесс упал сразу после `COMMIT` HTTP-запроса.

## Consumer

`app/broker/handlers.py` → `process_payment_event`:

1. Если статус `pending` — эмуляция шлюза (`app/services/gateway.py`).
2. Пишет `succeeded` / `failed` и `processed_at`.
3. Шлёт webhook (`app/services/webhook.py`).
4. Пишет `webhook_sent_at`.

Повторная доставка сообщения идемпотентна: шлюз не вызывается повторно для терминального статуса, webhook не шлётся, если `webhook_sent_at` уже заполнен.

## Retry и DLQ

Ошибка обработки (сеть, 5xx webhook после внутренних ретраев и т.д.):

| Попытка | Действие                                      |
|---------|-----------------------------------------------|
| 1       | обработка сразу из `payments.new`             |
| 2       | публикация в `payments.retry.1` (TTL 2с)      |
| 3       | публикация в `payments.retry.2` (TTL 4с)      |
| дальше  | `basic.reject(requeue=false)` → `payments.new.dlq` |

TTL-очереди dead-letter’ят сообщение обратно в `payments.new`. Счётчик попыток — заголовок `x-retry-count`.

Webhook внутри одной попытки: 3 HTTP-запроса с паузами 1с и 2с.

## Идемпотентность API

Хеш канонического JSON тела (`PaymentCreate.fingerprint`) хранится в `payments.request_hash` вместе с уникальным `idempotency_key`.

## Аутентификация

Сравнение `X-API-Key` с `settings.api_key` через `secrets.compare_digest`. Healthcheck и демо webhook-sink ключ не требуют.
