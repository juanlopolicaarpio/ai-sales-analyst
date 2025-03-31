import os
from pydantic import Field
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Application Settings
    APP_NAME: str = "AI Sales Analyst"
    APP_ENV: str = Field(default="development")
    DEBUG: bool = Field(default=True)
    LOG_LEVEL: str = Field(default="INFO")
    SECRET_KEY: str = Field(...)
    # Add these lines to your config.py file
# Authentication settings
    SECRET_KEY: str = Field(default="your-super-secret-key-change-this-in-production")
    ACCESS_TOKEN_EXPIRE_DAYS: int = Field(default=7)
    APP_URL: str = Field(default="http://localhost:8000")
    FRONTEND_URL: str = Field(default="http://localhost:3000")

    # API Settings
    HOST: str = Field(default="0.0.0.0")
    PORT: int = Field(default=8000)
    
    # Database Settings
    DATABASE_URL: str = Field(...)
    DATABASE_TEST_URL: Optional[str] = None
    
    # OpenAI API
    OPENAI_API_KEY: str = Field(...)
    
    # Slack Integration
    SLACK_BOT_TOKEN: Optional[str] = None
    SLACK_SIGNING_SECRET: Optional[str] = None
    
    # Twilio WhatsApp Integration
    TWILIO_ACCOUNT_SID: Optional[str] = None
    TWILIO_AUTH_TOKEN: Optional[str] = None
    TWILIO_PHONE_NUMBER: Optional[str] = None
    
    # Email Integration
    EMAIL_HOST: Optional[str] = None
    EMAIL_PORT: Optional[int] = None
    EMAIL_USERNAME: Optional[str] = None
    EMAIL_PASSWORD: Optional[str] = None
    EMAIL_FROM: Optional[str] = None
    
    # Shopify Integration
# Shopify Integration
    SHOPIFY_API_KEY: Optional[str] = None
    SHOPIFY_API_SECRET: Optional[str] = None
    SHOPIFY_STORE_URL: Optional[str] = None
    SHOPIFY_ACCESS_TOKEN: Optional[str] = None    
    # AWS Settings
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_REGION: Optional[str] = None
    
    # Redis Cache
    REDIS_URL: Optional[str] = None

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


# Create settings instance
settings = Settings()  # type: ignore


# Helper function to get database URL based on environment
def get_database_url() -> str:
    """Return the database URL based on the environment."""
    if settings.APP_ENV == "test" and settings.DATABASE_TEST_URL:
        return settings.DATABASE_TEST_URL
    return settings.DATABASE_URL