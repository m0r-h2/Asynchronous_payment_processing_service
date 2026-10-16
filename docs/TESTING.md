# Тесты

Юнит- и интеграционные тесты на SQLite (без PostgreSQL/RabbitMQ). Брокер и шлюз мокаются.

## Что покрыто

| Файл                         | Сценарии                                              |
|------------------------------|-------------------------------------------------------|
| `tests/test_api.py`          | 202, 401, 404, 409, 422, replay, GET                  |
| `tests/test_payment_service.py` | outbox в одной транзакции, конфликт ключа          |
| `tests/test_processing.py`   | шлюз, повторная обработка, пропуск webhook            |
| `tests/test_webhook.py`      | 3 попытки, успех после ошибок, исчерпание ретраев     |
| `tests/test_handlers.py`     | ack, retry queue, reject в DLQ                        |
| `tests/test_outbox.py`       | публикация и сохранение unpublished при ошибке брокера |
| `tests/test_gateway.py`      | 90/10 ветки эмуляции                                  |
| `tests/test_schemas.py`      | fingerprint, валидация Pydantic                       |
| `tests/test_topology.py`     | имена очередей, TTL, DLX                              |

## Запуск в Docker (рекомендуется)

Образ API на Python 3.12:

```bash
docker compose --profile test run --rm tests
```

## Локально

Нужен Python 3.12 (в системном 3.14 часть колёс может не ставиться):

```bash
pip install -r requirements-dev.txt
pytest -q
```

С подробностями:

```bash
pytest -vv
```
