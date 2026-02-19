from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parent.parent / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ZhituAPI
    zhitu_token: str = ""
    zhitu_base_url: str = "https://api.zhituapi.com"
    zhitu_rate_limit: int = 3000
    zhitu_timeout: int = 10
    zhitu_max_retries: int = 3

    # SQLite（本地信号存储）
    database_url: str = "sqlite:///./tide_watcher.db"

    # MySQL（历史数据源）
    mysql_host: str = "localhost"
    mysql_port: int = 3306
    mysql_user: str = "root"
    mysql_password: str = ""
    mysql_database: str = "xuangusystem"

    # App
    app_env: str = "development"
    app_port: int = 8000

    @property
    def is_dev(self) -> bool:
        return self.app_env == "development"


settings = Settings()
