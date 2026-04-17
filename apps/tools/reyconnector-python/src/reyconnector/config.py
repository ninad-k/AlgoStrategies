from pydantic_settings import BaseSettings, SettingsConfigDict


class WebhookSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="REYCONNECTOR_", env_file=".env", extra="ignore")

    control_api_base_url: str = "http://localhost:5241"
