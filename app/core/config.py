from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "BuddyBloom API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"

    # Supabase Settings
    SUPABASE_URL: str
    SUPABASE_KEY: str
    SUPABASE_SERVICE_KEY: str = ""  # Optional: service_role key for admin user creation
    SUPABASE_JWT_SECRET: str

    # Firebase Settings
    FIREBASE_PROJECT_ID: str = "buddybloom-app"

    # AI API Keys
    OPENAI_API_KEY: str = ""

    # Database
    DATABASE_URL: str

    # SMTP Email configuration
    SMTP_EMAIL: str = ""
    SMTP_PASSWORD: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
