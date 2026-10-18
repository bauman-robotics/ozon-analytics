#!/usr/bin/env python3
"""CLI: проверка ключа, сбор данных, демо и сборка дашборда.

Примеры:
    py run.py check
    py run.py collect --days 30
    py run.py report
    py run.py demo
    py run.py all --days 30
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from ozon import api, calc, calcpage, collect as collector, demo, metrics, report, store
from ozon.client import OzonAPIError, OzonClient
from ozon.config import DEFAULT_ENV, ROOT, Settings
from ozon.util import fmt_money, fmt_pct

COSTS_FILE = ROOT / "costs.csv"


def _costs_path(args: argparse.Namespace) -> Path | None:
    if getattr(args, "costs", None):
        return Path(args.costs)
    return COSTS_FILE if COSTS_FILE.exists() else None


def _build_report(
    snapshot: dict,
    args: argparse.Namespace,
    filename: str = "dashboard.html",
    suffix: str = "",
) -> Path:
    costs = metrics.load_costs(_costs_path(args))
    data = metrics.build(snapshot, costs)
    html_text = report.render(data)
    path = store.save_text(html_text, filename)
    for csv_path in report.write_csvs(data, store.OUT_DIR, suffix):
        print(f"  CSV: {csv_path.relative_to(ROOT)}")
    kpi = data["kpi"]
    print(
        f"  Выручка: {fmt_money(kpi['revenue'])} · заказов: {kpi['units']:.0f} шт · "
        f"возвраты: {fmt_pct(kpi['return_rate'])} · алертов: {len(data['alerts'])}"
    )
    return path


def _mask(value: str, keep: int = 4) -> str:
    value = (value or "").strip()
    if not value:
        return "—"
    if len(value) <= keep:
        return value
    return "…" + value[-keep:]


def cmd_check(args: argparse.Namespace) -> int:
    env_path = Path(args.env) if getattr(args, "env", None) else DEFAULT_ENV
    settings = Settings.from_env(env_path)
    key = (settings.api_key or "").strip()

    print("Проверка настроек:", flush=True)
    print(f"  .env: {env_path} — {'найден' if env_path.exists() else 'НЕ НАЙДЕН'}", flush=True)
    print(f"  Client-Id: {_mask(settings.client_id)} ({len(settings.client_id)} симв.)", flush=True)
    print(f"  Api-Key: {len(key)} симв." if key else "  Api-Key: пусто", flush=True)

    if not settings.configured:
        print("\nНе хватает данных. Создайте файл .env рядом с run.py:", flush=True)
        print("  OZON_CLIENT_ID=123456", flush=True)
        print("  OZON_API_KEY=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx", flush=True)
        print("Подробно: README → «API-ключ: как создать и куда положить».", flush=True)
        if env_path.suffix == ".txt" or env_path.name != ".env":
            print(f"Внимание: ожидается файл с именем ровно '.env', а передан '{env_path.name}'.", flush=True)
        return 2

    if " " in key:
        print("  ! В ключе есть пробел — скопируйте ключ целиком, без пробелов.", flush=True)
    if key.isdigit():
        print("  ! Ключ похож на Client-Id — возможно, значения перепутаны местами.", flush=True)
    if len(key) < 20:
        print("  ! Ключ подозрительно короткий — вероятно, скопирован не полностью.", flush=True)

    if args.offline:
        print("\nРежим --offline: запрос к API не выполняется, настройки прочитаны.", flush=True)
        return 0

    print(f"\nЗапрос к {settings.base_url}/v1/roles (таймаут {args.timeout} с)…", flush=True)
    client = OzonClient(
        settings.client_id,
        settings.api_key,
        base_url=settings.base_url,
        timeout=args.timeout,
        rps=settings.rps,
    )
    started = time.monotonic()
    try:
        roles = api.fetch_roles(client, attempts=1)
    except OzonAPIError as exc:
        elapsed = time.monotonic() - started
        print(f"Не удалось за {elapsed:.1f} с: {exc}", flush=True)
        text = str(exc).lower()
        if "нет связи" in text or "timed out" in text or "timeout" in text:
            print("\nПохоже, запрос не доходит до Ozon. Проверьте:", flush=True)
            print("  • интернет и VPN (Ozon API может блокироваться за пределами РФ);", flush=True)
            print("  • прокси/файрвол: нужен доступ к api-seller.ozon.ru по HTTPS;", flush=True)
            print("  • повторите с меньшим таймаутом: py run.py check --timeout 5", flush=True)
        return 1

    elapsed = time.monotonic() - started
    print(f"Ответ получен за {elapsed:.1f} с.", flush=True)
    print(f"Client-Id: {settings.client_id}")
    print(f"Ключ действует до: {roles.get('expires_at') or 'не указано'}")
    role_list = roles.get("roles") or []
    if not role_list:
        print("Роли не найдены — проверьте ключ.", flush=True)
        return 1
    total_methods = 0
    for role in role_list:
        methods = role.get("methods") or []
        total_methods += len(methods)
        sample = ", ".join(methods[:4]) + ("…" if len(methods) > 4 else "")
        print(f"  • {role.get('name')}: {len(methods)} методов ({sample})")
    print(f"Всего методов доступно: {total_methods}")

    info = api.fetch_seller_info(client)
    if "error" not in info:
        company = (info.get("result") or {}).get("company_name") or info.get("company_name")
        if company:
            print(f"Компания: {company}")
    return 0


def cmd_collect(args: argparse.Namespace) -> int:
    settings = Settings.from_env()
    if not settings.configured:
        print("Нет ключа: заполните .env (OZON_CLIENT_ID, OZON_API_KEY).")
        return 2
    try:
        snapshot = collector.collect(
            settings,
            days=args.days,
            include_stocks=not args.no_stocks,
            include_finance=not args.no_finance,
            include_turnover=not args.no_turnover,
            include_today=getattr(args, "include_today", False),
        )
    except OzonAPIError as exc:
        print(f"Ошибка API: {exc}")
        return 1

    path = store.save(snapshot, args.snapshot or store.DEFAULT_SNAPSHOT)
    print(f"Снимок сохранён: {path}")
    for warning in snapshot["meta"].get("warnings") or []:
        print(f"  ! {warning}")
    print(f"Строк данных: {len(snapshot.get('rows') or [])} · запросов к API: {snapshot['meta']['api_calls']}")

    if getattr(args, "report", False):
        try:
            out = _build_report(snapshot, args)
            print(f"Дашборд: {out}")
        except Exception as exc:  # noqa: BLE001 - показываем пользователю причину
            print(f"Не удалось собрать дашборд: {exc}")
            return 1
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    try:
        snapshot = store.load(args.snapshot or store.DEFAULT_SNAPSHOT)
    except FileNotFoundError as exc:
        print(exc)
        return 2
    out = _build_report(snapshot, args)
    print(f"Готово: {out}")
    print(f"Откройте в браузере: file://{out}")
    return 0


def cmd_demo(args: argparse.Namespace) -> int:
    snapshot = demo.make_snapshot(days=args.days, seed=args.seed)
    path = store.save(snapshot, store.DATA_DIR / "demo_snapshot.json")
    print(f"Демо-снимок: {path}")
    out = _build_report(snapshot, args, filename="dashboard-demo.html", suffix="-demo")
    print(f"Готово: {out}")
    print(f"Откройте в браузере: file://{out}")
    return 0


def cmd_all(args: argparse.Namespace) -> int:
    args.report = True
    return cmd_collect(args)


def cmd_calc(args: argparse.Namespace) -> int:
    if getattr(args, "demo", False):
        demo_path = store.DATA_DIR / "demo_snapshot.json"
        snapshot = store.load(demo_path) if demo_path.exists() else demo.make_snapshot(days=args.days)
    else:
        try:
            snapshot = store.load(args.snapshot or store.DEFAULT_SNAPSHOT)
        except FileNotFoundError as exc:
            print(exc)
            print("Или посмотрите калькулятор на демо-данных: py run.py calc --demo")
            return 2

    costs = metrics.load_costs(_costs_path(args))
    data = metrics.build(snapshot, costs)
    model = calc.build_model(data, costs)
    if not model["skus"]:
        print("Нет товаров с продажами за период — нечего считать.")
        return 1

    path = store.save_text(calcpage.render(model), "calculator.html")
    print(f"Товаров: {len(model['skus'])} · комиссия {model['commission_rate'] * 100:.1f}% · "
          f"реклама {model['ad_rate'] * 100:.1f}%")
    print(f"Готово: {path}")
    print(f"Откройте в браузере: file://{path}")
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    store.ensure_dirs()
    from ozon.server import serve

    serve(store.OUT_DIR, port=args.port)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run.py",
        description="Аналитика Ozon Seller API: сбор данных и HTML-дашборд",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_check = sub.add_parser("check", help="проверить ключ, роли и срок действия")
    p_check.add_argument("--offline", action="store_true", help="только прочитать .env, без запроса к API")
    p_check.add_argument("--timeout", type=int, default=15, help="таймаут запроса в секундах (по умолчанию 15)")
    p_check.add_argument("--env", help="путь к .env (по умолчанию рядом с run.py)")
    p_check.set_defaults(func=cmd_check)

    p_collect = sub.add_parser("collect", help="собрать данные в снимок")
    p_collect.add_argument("--days", type=int, default=30, help="глубина периода (по умолчанию 30)")
    p_collect.add_argument("--snapshot", help="куда сохранить снимок (по умолчанию data/snapshot.json)")
    p_collect.add_argument("--costs", help="CSV с себестоимостью")
    p_collect.add_argument("--report", action="store_true", help="сразу собрать дашборд")
    p_collect.add_argument("--no-stocks", action="store_true", help="не запрашивать остатки")
    p_collect.add_argument("--no-finance", action="store_true", help="не запрашивать финансы")
    p_collect.add_argument("--no-turnover", action="store_true", help="не запрашивать оборачиваемость")
    p_collect.add_argument("--include-today", action="store_true", help="включить неполный текущий день")
    p_collect.set_defaults(func=cmd_collect)

    p_report = sub.add_parser("report", help="собрать дашборд из готового снимка")
    p_report.add_argument("--snapshot", help="путь к снимку")
    p_report.add_argument("--costs", help="CSV с себестоимостью")
    p_report.set_defaults(func=cmd_report)

    p_demo = sub.add_parser("demo", help="демо-данные и дашборд без ключа")
    p_demo.add_argument("--days", type=int, default=30)
    p_demo.add_argument("--seed", type=int, default=42)
    p_demo.add_argument("--costs", help="CSV с себестоимостью")
    p_demo.set_defaults(func=cmd_demo)

    p_all = sub.add_parser("all", help="collect + report одной командой")
    p_all.add_argument("--days", type=int, default=30)
    p_all.add_argument("--snapshot", help="путь к снимку")
    p_all.add_argument("--costs", help="CSV с себестоимостью")
    p_all.add_argument("--no-stocks", action="store_true")
    p_all.add_argument("--no-finance", action="store_true")
    p_all.add_argument("--no-turnover", action="store_true")
    p_all.add_argument("--include-today", action="store_true")
    p_all.set_defaults(func=cmd_all)

    p_calc = sub.add_parser("calc", help="калькулятор прибыли по сценариям")
    p_calc.add_argument("--snapshot", help="путь к снимку")
    p_calc.add_argument("--costs", help="CSV с себестоимостью")
    p_calc.add_argument("--demo", action="store_true", help="считать на демо-данных")
    p_calc.add_argument("--days", type=int, default=30, help="период для демо-снимка")
    p_calc.set_defaults(func=cmd_calc)

    p_serve = sub.add_parser("serve", help="локальный сервер для папки out/")
    p_serve.add_argument("--port", type=int, default=8765)
    p_serve.set_defaults(func=cmd_serve)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
