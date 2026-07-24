from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    groq_api_key: str = ""
    supabase_url: str
    supabase_service_key: str
    jwt_secret_key: str

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()