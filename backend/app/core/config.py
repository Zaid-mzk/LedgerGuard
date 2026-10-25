from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str = "postgresql+psycopg://ledgerguard:ledgerguard@localhost:5432/ledgerguard"
    jwt_secret: str = "development-only-change-this-secret"
    jwt_access_token_minutes: int = 20
    frontend_origin: str = "http://localhost:5173"
    seed_demo_data: bool = False
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
