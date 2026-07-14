"""Wave 0.4 冒烟：pytest 能收集并执行；应用模块可导入。"""

from app.core.config import settings
from app.main import app


def test_app_is_fastapi() -> None:
    assert app.title == "知岸 API"
    assert app.version == "0.12.0"


def test_settings_database_url_default() -> None:
    assert settings.database_url.startswith("postgresql")
