from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    api_key: str = "dev-api-key"
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/payments"
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"
    outbox_poll_interval_sec: float = 0.5
    log_level: str = "INFO"
    webhook_timeout_sec: float = 10.0


settings = Settings()
