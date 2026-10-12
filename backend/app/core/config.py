from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "dev"  # dev | test | prod
    database_url: str = "postgresql+asyncpg://societypass:societypass@localhost:5432/societypass"

    # --- security ---
    jwt_secret: str = "dev-jwt-secret-change-me-dev-jwt-secret"
    qr_secret: str = "dev-qr-secret-change-me-dev-qr-secret"
    access_token_ttl_minutes: int = 30
    refresh_token_ttl_days: int = 30
    cors_origins: str = "*"

    # --- OTP ---
    otp_provider: str = "console"  # console | msg91
    otp_ttl_seconds: int = 300
    otp_length: int = 6
    otp_max_attempts: int = 5
    otp_per_phone_per_hour: int = 5
    otp_resend_cooldown_seconds: int = 30
    otp_per_ip_per_hour: int = 30
    # dev conveniences (ignored when env == prod)
    otp_fixed_code: str = ""  # e.g. "123456" for demos
    otp_dev_echo: bool = False  # return the OTP in the API response
    msg91_auth_key: str = ""
    msg91_template_id: str = ""

    # --- storage ---
    storage_backend: str = "local"  # local | s3 | memory
    local_storage_dir: str = "./local_storage"
    api_public_url: str = "http://localhost:8000"
    s3_endpoint_url: str = ""  # MinIO / R2 endpoint used by the API
    s3_public_endpoint_url: str = ""  # endpoint embedded in presigned URLs (reachable by phones)
    s3_region: str = "auto"
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_public_bucket: str = "societypass-public"
    s3_private_bucket: str = "societypass-private"
    s3_public_base_url: str = ""  # e.g. http://192.168.1.5:9000/societypass-public
    presign_put_ttl_seconds: int = 600
    presign_get_ttl_seconds: int = 300

    # --- business rules ---
    pending_order_ttl_hours: int = 48
    app_deep_link_scheme: str = "societypass"
    app_web_domain: str = "https://societypass.app"
    max_screenshot_bytes: int = 5 * 1024 * 1024
    max_image_bytes: int = 10 * 1024 * 1024
    background_jobs: bool = True

    # --- platform ---
    super_admin_phones: str = ""
    expo_push_url: str = "https://exp.host/--/api/v2/push/send"
    default_country_code: str = "+91"

    @field_validator("database_url")
    @classmethod
    def _async_driver(cls, v: str) -> str:
        if v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v

    @property
    def is_prod(self) -> bool:
        return self.env == "prod"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def super_admin_phone_list(self) -> list[str]:
        return [p.strip() for p in self.super_admin_phones.split(",") if p.strip()]


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    if s.is_prod and (s.jwt_secret.startswith("dev-") or s.qr_secret.startswith("dev-")):
        raise RuntimeError("JWT_SECRET and QR_SECRET must be set in production")
    return s
