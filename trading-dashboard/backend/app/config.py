from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    super_admin_email: str = "admin@reycapital.com"
    super_admin_password: str = "changeme123"
    cors_origins: str = "http://localhost:3000"
    # Shared secret for MT5 Expert Advisor WebRequest (header X-MT5-Token). If empty, MT5 GET is disabled.
    mt5_execution_secret: str = ""

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

    class Config:
        env_file = ".env"


settings = Settings()
