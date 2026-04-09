from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    openai_api_key: str = ""
    google_api_key: str = ""
    github_token: str = ""
    supabase_url: str = ""
    supabase_service_key: str = ""
    database_url: str = ""
    app_env: str = "development"
    gemini_chat_model: str = "gemini-2.5-flash"
    gemini_embedding_model: str = "models/gemini-embedding-001"
    allowed_origins: str = "*"  # comma-separated list, e.g. "https://app.vercel.app,http://localhost:5173"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
