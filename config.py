"""
Configuration for Inbox Worker
"""
from pydantic_settings import BaseSettings
from pydantic import field_validator


class Settings(BaseSettings):
    app_name: str = "Inbox Worker"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8006

    # Gmail OAuth2 (scopes: gmail.readonly + gmail.compose)
    gmail_account: str = "contact@pompiers34800.com"
    gmail_client_id: str = ""
    gmail_client_secret: str = ""
    gmail_refresh_token: str = ""

    # Supabase Storage (pour stocker les pièces jointes reçues)
    supabase_url: str = ""    # injecter via .env — ex: SUPABASE_URL=https://<ref>.supabase.co
    supabase_key: str = ""    # service_role key (pas anon) — injecter via .env

    # Inter-worker auth
    worker_auth_key: str = "flowchat-internal-secret"

    @field_validator("worker_auth_key", mode="before")
    @classmethod
    def strip_worker_auth_key(cls, v: str) -> str:
        return str(v).split()[0] if v else v

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
