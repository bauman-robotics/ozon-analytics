"""Сбор снимка данных: продажи, воронка, остатки, финансы."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Callable

from . import api, finance as finance_api
from .client import OzonAPIError, OzonClient
from .config import Settings
from .util import iso_day, to_int, utc_now_iso


def _merge(rows: list[dict], patch: list[dict]) -> list[dict]:
    """Склеивает строки по (sku, day)."""
    index: dict[tuple, dict] = {}
    for row in rows:
        key = (to_int(row.get("sku")), str(row.get("day")))
        index[key] = row
    for row in patch:
        key = (to_int(row.get("sku")), str(row.get("day")))
        target = index.get(key)
        if target is None:
            index[key] = row
        else:
            for field, value in row.items():
                if field in ("sku", "day", "name") and target.get(field):
                    continue
                target[field] = value
    return list(index.values())


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
    today = date.today()
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
        warnings.append(f"Аналитика продаж: {exc}")

    log("2/4 Воронка и показы…")
    funnel = None
    last_error: OzonAPIError | None = None
    for index, metrics_set in enumerate((api.FUNNEL_METRICS, api.FUNNEL_FALLBACK)):
        try:
            funnel = api.fetch_analytics_data(
                client, prev_from, period_to, metrics_set, ["sku", "day"]
            )
            if index > 0:
                warnings.append(
                    "Воронка: Ozon отклонил часть метрик, загружены только сессии — "
                    "конверсия в корзину будет недоступна"
                )
            break
        except OzonAPIError as exc:
            last_error = exc
            if "deprecated" not in str(exc).lower():
                break
    if funnel is None:
        warnings.append(f"Воронка: {last_error}")
    else:
        rows = _merge(rows, funnel)

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
