"""Сбор снимка данных: продажи, остатки, оборачиваемость, финансы.

Воронка не собирается: Ozon отключил её метрики (см. ozon/api.py).
"""

from __future__ import annotations

from datetime import timedelta
from typing import Callable

from . import api, finance as finance_api
from .client import OzonAPIError, OzonClient
from .config import Settings
from .util import iso_day, to_int, utc_now_iso, utc_today


def collect(
    settings: Settings,
    days: int = 30,
    *,
    log: Callable[[str], None] = print,
    include_stocks: bool = True,
    include_finance: bool = True,
    include_turnover: bool = True,
    include_today: bool = False,
) -> dict:
    client = OzonClient(
        settings.client_id,
        settings.api_key,
        base_url=settings.base_url,
        timeout=settings.timeout,
        rps=settings.rps,
    )
    warnings: list[str] = []
    today = utc_today()
    # Данные за сегодня всегда неполные (аналитика обновляется 2 раза в сутки),
    # поэтому по умолчанию берём период по вчерашний день.
    period_to = today if include_today else today - timedelta(days=1)
    period_from = period_to - timedelta(days=days - 1)
    prev_to = period_from - timedelta(days=1)
    prev_from = prev_to - timedelta(days=days - 1)

    log(f"Период: {iso_day(period_from)} … {iso_day(period_to)} (сравнение с {iso_day(prev_from)} … {iso_day(prev_to)})")

    log("1/4 Аналитика продаж…")
    rows: list[dict] = []
    try:
        rows = api.fetch_analytics_data(
            client, prev_from, period_to, api.SALES_METRICS, ["sku", "day"]
        )
    except OzonAPIError as exc:
        if exc.status in (400, 403):
            warnings.append(
                f"Аналитика продаж: Ozon отклонил расширенный набор метрик ({exc}); "
                "пробую только выручку и заказы"
            )
            try:
                rows = api.fetch_analytics_data(
                    client, prev_from, period_to, api.SALES_FALLBACK_METRICS, ["sku", "day"]
                )
            except OzonAPIError as fallback_exc:
                warnings.append(f"Аналитика продаж: {fallback_exc}")
            else:
                warnings.append(
                    "Аналитика продаж: загружены только выручка и заказы — "
                    "возвраты, отмены и доставка недоступны (нужен Premium Plus)"
                )
        else:
            warnings.append(f"Аналитика продаж: {exc}")

    # Воронку не запрашиваем: Ozon отключил session_view/hits_view/hits_tocart
    # и отвечает HTTP 400 на весь запрос. Подробности — в ozon/api.py.
    log("2/4 Воронка: Ozon отключил метрики воронки — пропускаю")

    current_rows = [r for r in rows if str(r.get("day")) >= iso_day(period_from)]

    stocks: dict[int, dict] = {}
    if include_stocks and current_rows:
        log("3/4 Остатки по складам…")
        skus = sorted({to_int(r.get("sku")) for r in current_rows if to_int(r.get("sku"))})
        try:
            stocks = api.fetch_stocks(client, skus)
        except OzonAPIError as exc:
            warnings.append(f"Остатки: {exc}")

    turnover: dict[int, dict] = {}
    if include_turnover:
        try:
            turnover = api.fetch_turnover(client)
        except OzonAPIError as exc:
            warnings.append(f"Оборачиваемость: {exc}")

    finance: dict = {}
    if include_finance:
        log("4/4 Финансы…")
        try:
            finance = finance_api.fetch(client, period_from, period_to)
            log(f"    начислений: {finance.get('accruals_count', 0)}")
        except OzonAPIError as exc:
            warnings.append(f"Начисления (accrual): {exc}; пробую старый метод totals")
            try:
                finance = api.fetch_finance_totals(client, period_from, period_to)
                finance["source"] = "transaction_totals"
            except OzonAPIError as fallback_error:
                warnings.append(f"Финансы: {fallback_error}")

    warnings.extend(client.warnings)

    snapshot = {
        "meta": {
            "generated_at": utc_now_iso(),
            "mode": "live",
            "client_id_masked": _mask(settings.client_id),
            "days": days,
            "period": {"from": iso_day(period_from), "to": iso_day(period_to)},
            "prev_period": {"from": iso_day(prev_from), "to": iso_day(prev_to)},
            "api_calls": client.calls,
            "warnings": warnings,
        },
        "rows": [_round_row(r) for r in rows],
        "stocks": {str(k): v for k, v in stocks.items()},
        "turnover": {str(k): v for k, v in turnover.items()},
        "finance": finance,
    }
    return snapshot


def _round_row(row: dict) -> dict:
    result = {}
    for key, value in row.items():
        if isinstance(value, float):
            result[key] = round(value, 4)
        else:
            result[key] = value
    return result


def _mask(value: str) -> str:
    value = (value or "").strip()
    if len(value) <= 4:
        return value or "—"
    return "…" + value[-4:]


def collect_month_finance(settings: Settings, year: int, month: int) -> list[dict]:
    client = OzonClient(settings.client_id, settings.api_key, timeout=settings.timeout)
    return api.fetch_realization(client, year, month)
