from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # App
    secret_key: str = "change-this-secret-key-in-production"
    app_host: str = "0.0.0.0"
    app_port: int = 8080
    debug: bool = False

    # PostgreSQL
    postgres_user: str = "clouduser"
    postgres_password: str = "cloudpass"
    postgres_db: str = "clouddb"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    # Redis
    redis_password: str = "redispass"
    redis_host: str = "localhost"
    redis_port: int = 6380

    # MinIO
    minio_root_user: str = "minioadmin"
    minio_root_password: str = "minioadmin123"
    minio_host: str = "localhost"
    minio_port: int = 9002
    minio_bucket: str = "cloud-storage"

    # Quota
    default_quota_bytes: int = 1073741824  # 1 GB

    # JWT
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def redis_url(self) -> str:
        return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/0"

    class Config:
        env_file = ".env"


settings = Settings()
