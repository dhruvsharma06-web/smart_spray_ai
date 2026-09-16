from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "Smart Farming Assistant Backend"
    environment: str = "development"
    database_url: str = "postgresql+psycopg://smartspray:smartspray@localhost:5432/smartspray"
    jwt_secret_key: str = "change-this-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    max_image_bytes: int = 10 * 1024 * 1024
    storage_dir: str = "storage/images"
    ai_service_url: str = "http://localhost:8001"
    decision_service_url: str = "http://localhost:8002"
    genai_service_url: str = "http://localhost:8003"
    weather_provider: str = "mock"
    log_level: str = "INFO"
    decision_ttl_seconds: int = 300
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
