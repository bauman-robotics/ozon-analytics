"""Загрузка настроек из .env / переменных окружения."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ENV = ROOT / ".env"


def load_env(path: Path | None = None, override: bool = False) -> dict[str, str]:
    """Простой парсер .env: KEY=VALUE, комментарии через #, кавычки необязательны."""
    path = Path(path or DEFAULT_ENV)
    values: dict[str, str] = {}
    if not path.exists():
        return values
    # utf-8-sig: блокнот Windows может сохранить файл с BOM
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key.lower().startswith("export "):
            key = key[7:].strip()
        value = value.strip().strip('"').strip("'")
        if not key:
            continue
        values[key] = value
        if override or key not in os.environ:
            os.environ[key] = value
    return values


@dataclass(frozen=True)
class Settings:
    client_id: str = ""
    api_key: str = ""
    timeout: int = 30
    rps: float = 10.0          # запросов в секунду (лимит Ozon — 50)
    base_url: str = "https://api-seller.ozon.ru"

    @property
    def configured(self) -> bool:
        return bool(self.client_id.strip() and self.api_key.strip())

    @classmethod
    def from_env(cls, path: Path | None = None) -> "Settings":
        load_env(path)
        return cls(
            client_id=os.getenv("OZON_CLIENT_ID", "").strip(),
            api_key=os.getenv("OZON_API_KEY", "").strip(),
            timeout=int(os.getenv("OZON_TIMEOUT", "30") or 30),
            rps=float(os.getenv("OZON_RPS", "10") or 10),
            base_url=os.getenv("OZON_BASE_URL", "https://api-seller.ozon.ru").rstrip("/"),
        )
