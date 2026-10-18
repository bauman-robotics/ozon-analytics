"""Сохранение и загрузка снимков данных."""

from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
OUT_DIR = ROOT / "out"
DEFAULT_SNAPSHOT = DATA_DIR / "snapshot.json"


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)


def save(snapshot: dict, path: Path | str = DEFAULT_SNAPSHOT) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(snapshot, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, path)
    return path


def load(path: Path | str = DEFAULT_SNAPSHOT) -> dict:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"Нет файла данных {path}. Сначала выполните: py run.py collect "
            f"(или py run.py demo)"
        )
    return json.loads(path.read_text(encoding="utf-8"))


def save_text(text: str, filename: str) -> Path:
    ensure_dirs()
    path = OUT_DIR / filename
    path.write_text(text, encoding="utf-8")
    return path
