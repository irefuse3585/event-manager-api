from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = Field(
        ...,
        description="Database URL",
        examples=["postgresql+asyncpg://user:pass@localhost/db"],
    )
    REDIS_URL: str = Field(
        ..., description="Redis URL", examples=["redis://localhost:6379"]
    )

    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        30, description="JWT access token expiration time in minutes"
    )
    ACCESS_TOKEN_SECRET: str = Field(
        ..., description="Secret for access token generation"
    )
    ACCESS_TOKEN_ALGORITHM: str = Field(
        "HS256", description="Algorithm for access token generation"
    )

    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(
        7, description="JWT refresh token expiration time in days"
    )
    REFRESH_TOKEN_SECRET: str = Field(
        ..., description="Secret for refresh token generation"
    )
    REFRESH_TOKEN_ALGORITHM: str = Field(
        "HS256", description="Algorithm for refresh token generation"
    )

    RATE_LIMIT_LOGIN: str = Field("5/minute", description="Login attempt rate limit")
    RATE_LIMIT_REFRESH: str = Field(
        "30/minute", description="Refresh token request rate limit"
    )

    ENABLE_MSGPACK: bool = Field(True, description="Enable MessagePack serialization")

    JWT_ISSUER: str = Field("neofi-event-api", description="JWT issuer")
    JWT_AUDIENCE: str = Field("neofi-client-app", description="JWT audience")

    ENVIRONMENT: str = Field("production", description="App environment")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()  # type: ignore[call-arg]
