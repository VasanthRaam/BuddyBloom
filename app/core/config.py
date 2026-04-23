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

    # Database
    DATABASE_URL: str

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
