# HTTP API

Базовый URL: `http://localhost:8000`

Все эндпоинты `/api/v1/*` требуют заголовок `X-API-Key`. Значение по умолчанию — `dev-api-key` (переменная `API_KEY`).

Интерактивная схема: [http://localhost:8000/docs](http://localhost:8000/docs)

## Заголовки

| Заголовок         | Где обязателен              | Описание                                      |
|-------------------|-----------------------------|-----------------------------------------------|
| `X-API-Key`       | все `/api/v1/*`             | Статический ключ доступа                      |
| `Idempotency-Key` | `POST /api/v1/payments`     | 1–255 символов, защита от повторной отправки  |

Повтор `POST` с тем же `Idempotency-Key` и тем же JSON-телом возвращает исходный платёж (`202`).  
То же ключ, но другое тело — `409 Conflict`.

## Эндпоинты

### `POST /api/v1/payments`

Создаёт платёж в статусе `pending`, в той же транзакции пишет запись в outbox. Ответ сразу, обработка асинхронная.

**Body**

```json
{
  "amount": "199.90",
  "currency": "RUB",
  "description": "Order 1001",
  "metadata": {"order_id": "1001"},
  "webhook_url": "https://merchant.example/hooks/payments"
}
```

| Поле          | Тип                         | Ограничения                          |
|---------------|-----------------------------|--------------------------------------|
| `amount`      | decimal string              | `> 0`, максимум 2 знака после запятой |
| `currency`    | enum                        | `RUB`, `USD`, `EUR`                  |
| `description` | string                      | 1–512 символов                       |
| `metadata`    | object                      | произвольный JSON, по умолчанию `{}` |
| `webhook_url` | url                         | `http` или `https`                   |

**Ответ `202 Accepted`**

```json
{
  "payment_id": "8b1c3d2e-2f4a-4b6c-9d0e-1a2b3c4d5e6f",
  "status": "pending",
  "created_at": "2026-10-14T12:00:00.000000Z"
}
```

### `GET /api/v1/payments/{payment_id}`

Возвращает текущее состояние платежа.

**Ответ `200 OK`**

```json
{
  "id": "8b1c3d2e-2f4a-4b6c-9d0e-1a2b3c4d5e6f",
  "amount": "199.90",
  "currency": "RUB",
  "description": "Order 1001",
  "metadata": {"order_id": "1001"},
  "status": "succeeded",
  "idempotency_key": "order-1001",
  "webhook_url": "https://merchant.example/hooks/payments",
  "created_at": "2026-10-14T12:00:00.000000Z",
  "processed_at": "2026-10-14T12:00:04.000000Z",
  "webhook_sent_at": "2026-10-14T12:00:04.100000Z"
}
```

`status`: `pending` → `succeeded` | `failed` после обработки consumer (обычно 2–5 секунд).

### Служебные

| Метод | Путь            | Auth | Назначение                                      |
|-------|-----------------|------|-------------------------------------------------|
| GET   | `/health`       | нет  | liveness для Docker healthcheck                 |
| POST  | `/webhook-sink` | нет  | демо-приёмник webhook, пишет тело в логи `api`  |

## Коды ошибок

| HTTP | Когда                                              |
|------|----------------------------------------------------|
| 401  | нет или неверный `X-API-Key`                       |
| 404  | платёж не найден                                   |
| 409  | `Idempotency-Key` уже использован с другим телом   |
| 422  | валидация body или отсутствует `Idempotency-Key`   |

## Webhook, который получит мерчант

`POST {webhook_url}` JSON:

```json
{
  "payment_id": "8b1c3d2e-2f4a-4b6c-9d0e-1a2b3c4d5e6f",
  "status": "succeeded",
  "amount": "199.90",
  "currency": "RUB",
  "description": "Order 1001",
  "metadata": {"order_id": "1001"},
  "processed_at": "2026-10-14T12:00:04.000000Z"
}
```

Consumer ожидает HTTP 2xx. Иначе webhook ретраится 3 раза, затем ретраится всё сообщение (до DLQ).

## Примеры

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

curl -s http://localhost:8000/api/v1/payments/<payment_id> \
  -H "X-API-Key: dev-api-key"
```
