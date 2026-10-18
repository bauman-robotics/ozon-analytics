#!/usr/bin/env python3
"""Синтетические скриншоты для README.

Собирает демо-данные (`run.py demo`) и калькулятор (`run.py calc --demo`),
затем рендерит готовые HTML-страницы в PNG через Playwright/Chromium.
Реальные данные и ключ Ozon не используются.

Установка (только для генерации скриншотов, не для работы проекта):

    python3 -m pip install -r scripts/requirements-screenshots.txt
    python3 -m playwright install chromium

Запуск:

    python3 scripts/make_screenshots.py

Если Chromium уже установлен в системе или лежит в кеше Playwright:

    CHROMIUM_PATH=/usr/bin/chromium python3 scripts/make_screenshots.py
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "out"
DOCS_DIR = ROOT / "docs"


def build_demo(days: int, seed: int) -> None:
    """Пересобирает демо-отчёт и калькулятор, чтобы скриншоты были свежими."""
    print("Собираю демо-данные…", flush=True)
    subprocess.run(
        [sys.executable, str(ROOT / "run.py"), "demo", "--days", str(days), "--seed", str(seed)],
        check=True,
        cwd=ROOT,
    )
    subprocess.run(
        [sys.executable, str(ROOT / "run.py"), "calc", "--demo"],
        check=True,
        cwd=ROOT,
    )


def find_chromium() -> str | None:
    """Ищет Chromium: env, системные имена, кеш Playwright."""
    candidates: list[str] = []
    env_path = os.environ.get("CHROMIUM_PATH")
    if env_path:
        candidates.append(env_path)
    for name in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable"):
        found = shutil.which(name)
        if found:
            candidates.append(found)
    for path in sorted((Path.home() / ".cache" / "ms-playwright").glob("chromium-*/chrome-linux*/chrome")):
        candidates.append(str(path))
    for candidate in candidates:
        if Path(candidate).exists():
            return candidate
    return None


def launch_browser(playwright):
    """Пробует браузер Playwright, затем системный/кешированный Chromium."""
    errors: list[str] = []
    for kwargs in ({}, {"args": ["--no-sandbox"]}):
        try:
            return playwright.chromium.launch(**kwargs)
        except Exception as exc:  # noqa: BLE001 - показываем причину в конце
            errors.append(str(exc).splitlines()[0])

    executable = find_chromium()
    if executable:
        for kwargs in (
            {"executable_path": executable},
            {"executable_path": executable, "args": ["--no-sandbox"]},
        ):
            try:
                return playwright.chromium.launch(**kwargs)
            except Exception as exc:  # noqa: BLE001
                errors.append(str(exc).splitlines()[0])

    raise RuntimeError(
        "Не удалось запустить Chromium. Установите браузер Playwright:\n"
        "  python3 -m playwright install chromium\n"
        "или укажите путь к системному Chromium:\n"
        "  CHROMIUM_PATH=/usr/bin/chromium python3 scripts/make_screenshots.py\n"
        f"Попытки: {errors}"
    )


def scroll_to(page, script: str) -> None:
    page.evaluate(script)
    page.wait_for_timeout(250)


def main() -> int:
    parser = argparse.ArgumentParser(description="Собрать синтетические скриншоты для README")
    parser.add_argument("--days", type=int, default=30, help="период демо-данных (по умолчанию 30)")
    parser.add_argument("--seed", type=int, default=42, help="seed демо-данных (по умолчанию 42)")
    parser.add_argument("--width", type=int, default=1280, help="ширина viewport (по умолчанию 1280)")
    parser.add_argument("--height", type=int, default=1000, help="высота viewport (по умолчанию 1000)")
    parser.add_argument("--no-build", action="store_true", help="не пересобирать демо-данные")
    args = parser.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(
            "Playwright не установлен. Установите:\n"
            "  python3 -m pip install -r scripts/requirements-screenshots.txt\n"
            "  python3 -m playwright install chromium",
            file=sys.stderr,
        )
        return 1

    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    if not args.no_build:
        build_demo(args.days, args.seed)

    dashboard = OUT_DIR / "dashboard-demo.html"
    calculator = OUT_DIR / "calculator.html"
    for path in (dashboard, calculator):
        if not path.exists():
            print(f"Нет файла {path}. Запустите без --no-build.", file=sys.stderr)
            return 1

    print("Рендерю скриншоты…", flush=True)
    with sync_playwright() as playwright:
        browser = launch_browser(playwright)
        page = browser.new_page(
            viewport={"width": args.width, "height": args.height},
            device_scale_factor=1,
        )

        page.goto(dashboard.as_uri())
        page.wait_for_load_state("load")
        page.evaluate("document.fonts.ready")
        page.wait_for_timeout(300)

        page.evaluate("window.scrollTo(0, 0)")
        page.wait_for_timeout(200)
        page.screenshot(path=str(DOCS_DIR / "dashboard-demo-1.png"))
        print(f"  {DOCS_DIR / 'dashboard-demo-1.png'}", flush=True)

        scroll_to(
            page,
            """
            const panel = [...document.querySelectorAll('.panel')]
                .find(el => el.textContent.includes('Заказы по дням'));
            if (panel) window.scrollTo(0, panel.getBoundingClientRect().top + window.scrollY - 12);
            """,
        )
        page.screenshot(path=str(DOCS_DIR / "dashboard-demo-2.png"))
        print(f"  {DOCS_DIR / 'dashboard-demo-2.png'}", flush=True)

        scroll_to(
            page,
            """
            const table = document.querySelector('#sku-table');
            if (table) {
                const panel = table.closest('.panel');
                window.scrollTo(0, panel.getBoundingClientRect().top + window.scrollY - 12);
            }
            """,
        )
        page.screenshot(path=str(DOCS_DIR / "dashboard-demo-3.png"))
        print(f"  {DOCS_DIR / 'dashboard-demo-3.png'}", flush=True)

        page.goto(calculator.as_uri())
        page.wait_for_load_state("load")
        page.evaluate("document.fonts.ready")
        page.wait_for_timeout(300)
        page.evaluate("window.scrollTo(0, 0)")
        page.wait_for_timeout(200)
        page.screenshot(path=str(DOCS_DIR / "calculator-demo.png"))
        print(f"  {DOCS_DIR / 'calculator-demo.png'}", flush=True)

        browser.close()

    print("Готово.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
