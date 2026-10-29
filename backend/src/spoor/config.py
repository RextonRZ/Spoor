"""Runtime settings. Secrets come from the environment / .env only and never reach clients (PRD §0.4)."""

from pathlib import Path

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Meta Model API — verified 2026-10-27 at https://dev.meta.ai/docs/models
    model_api_key: SecretStr | None = None
    meta_base_url: str = "https://api.meta.ai/v1"
    # Standard mode only for authorized surveillance footage (PRD §7.1); never the -contributor variant.
    spark_model: str = "muse-spark-1.3"
    sam_model: str = "sam-3.1"

    # Baseten Muse Spark Open — identifier must be confirmed against the live catalog (PRD §10.4)
    baseten_api_key: SecretStr | None = None
    baseten_base_url: str = "https://inference.baseten.co/v1"
    baseten_model_id: str | None = None

    data_dir: Path = Path("data")
    database_url: str | None = None  # default: sqlite file in data_dir; set a postgresql:// URL for Postgres

    # Which backend the Evidence/Hypothesis agents use: "meta" (Muse Spark 1.3), "baseten" (Muse Spark Open) or
    # "none" (deterministic orchestration only). Clip interpretation always uses Meta (video input).
    agent_backend: str = "meta"

    # Access control: JSON file {"tokens": {"<token>": {"user_id", "role", "site_ids"}}}. Never commit it.
    users_file: Path | None = None
    url_signing_secret: SecretStr | None = None
    signed_url_ttl_s: int = 300
    rate_limit_per_minute: int = 120

    # Optional extensions (PRD §5.4, step 11). Off until validated on held-out data.
    enable_multiview_xyz: bool = False
    enable_cross_camera_association: bool = False

    @field_validator("model_api_key", "baseten_api_key", "url_signing_secret", "baseten_model_id", "database_url",
                     "users_file", mode="before")
    @classmethod
    def _blank_is_unset(cls, v):
        """`KEY=` in .env means "not configured", never an empty secret (an empty HMAC key would sign links)."""
        return None if isinstance(v, str) and not v.strip() else v


def get_settings() -> Settings:
    return Settings()
