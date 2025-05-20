from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Database connection URL (e.g., PostgreSQL)
    DATABASE_URL: str

    # Redis connection URL for caching and messaging
    REDIS_URL: str

    # Secret key for JWT token generation
    JWT_SECRET: str

    # JWT Token expiration time in minutes (default 30)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Load settings from '.env' file automatically
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


# Singleton settings instance accessible throughout the application
settings = Settings()  # type: ignore[call-arg]
