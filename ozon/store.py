"""Сохранение и загрузка снимков данных."""

from __future__ import annotations

import json
import os
import stat
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, TextIO

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
OUT_DIR = ROOT / "out"
DEFAULT_SNAPSHOT = DATA_DIR / "snapshot.json"


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)


def _replace(tmp: Path, path: Path) -> None:
    """Атомарно заменяет файл; на Windows снимает атрибут «только чтение».

    Если файл открыт в Excel, Windows всё равно не даст его заменить — ошибка
    PermissionError уйдёт вызывающему коду, который покажет понятную подсказку.
    """
    try:
        os.replace(tmp, path)
    except PermissionError as first_error:
        if os.name != "nt":
            raise
        try:
            os.chmod(path, stat.S_IWRITE)
            os.replace(tmp, path)
        except OSError:
            # Отдаём исходную ошибку: она точнее объясняет, почему файл занят.
            raise first_error


@contextmanager
def atomic_open(
    path: Path | str,
    *,
    encoding: str = "utf-8",
    newline: str | None = None,
) -> Iterator[TextIO]:
    """Пишет во временный файл рядом и подменяет файл только после успешной записи.

    Так прерванный запуск не оставит половину CSV, а ошибка записи не затронет
    предыдущую версию файла.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    try:
        with tmp.open("w", encoding=encoding, newline=newline) as handle:
            yield handle
        _replace(tmp, path)
    finally:
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass


def save(snapshot: dict, path: Path | str = DEFAULT_SNAPSHOT) -> Path:
    path = Path(path)
    with atomic_open(path, encoding="utf-8") as handle:
        json.dump(snapshot, handle, ensure_ascii=False, indent=1)
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
    with atomic_open(path, encoding="utf-8") as handle:
        handle.write(text)
    return path
