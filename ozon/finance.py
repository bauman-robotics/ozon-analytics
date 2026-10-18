"""Финансы: новые методы /v1/finance/accrual/* с фолбэком на старые totals.

Старые /v3/finance/transaction/* отключаются, поэтому основной источник —
начисления по дням с курсорной пагинацией.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Iterable

from .client import OzonAPIError, OzonClient
from .util import iso_day, to_float, to_int

# Человекочитаемые названия групп
BUCKETS = {
    "commission": "Комиссия Ozon",
    "logistics": "Логистика",
    "last_mile": "Последняя миля",
    "reverse": "Обратная логистика",
    "returns": "Возвраты и отмены",
    "advertising": "Реклама",
    "storage": "Хранение",
    "acquiring": "Эквайринг",
    "packaging": "Упаковка",
    "inbound": "Приёмка поставки",
    "disposal": "Утилизация",
    "crossdock": "Кросс-докинг",
    "compensation": "Компенсации",
    "other": "Прочее",
}


def fetch_accrual_types(client: OzonClient) -> dict[int, str]:
    try:
        response = client.post("/v1/finance/accrual/types", {})
    except OzonAPIError:
        return {}
    result: dict[int, str] = {}
    for item in response.get("accrual_types") or []:
        result[to_int(item.get("id"))] = str(item.get("name") or "")
    return result


def fetch_accruals(
    client: OzonClient,
    date_from: date,
    date_to: date,
    *,
    max_pages_per_day: int = 200,
) -> list[dict]:
    """Начисления за период: по одному запросу на день + курсор last_id."""
    accruals: list[dict] = []
    current = date_from
    while current <= date_to:
        last_id = ""
        seen: set[str] = set()
        for _ in range(max_pages_per_day):
            response = client.post(
                "/v1/finance/accrual/by-day",
                {"date": iso_day(current), "last_id": last_id},
            )
            page = response.get("accruals") or []
            accruals.extend(page)
            last_id = str(response.get("last_id") or "")
            if not last_id or last_id in seen:
                break
            seen.add(last_id)
        current += timedelta(days=1)
    return accruals


def _money(value) -> float:
    if isinstance(value, dict):
        return to_float(value.get("amount"))
    return to_float(value)


def _bucket_for(type_name: str) -> str:
    name = (type_name or "").lower()
    mapping = (
        ("комисс", "commission"),
        ("обратн", "reverse"),
        ("последн", "last_mile"),
        ("логистик", "logistics"),
        ("возврат", "returns"),
        ("отмен", "returns"),
        ("компенсац", "compensation"),
        ("реклам", "advertising"),
        ("продвижен", "advertising"),
        ("хранен", "storage"),
        ("эквайринг", "acquiring"),
        ("упаковк", "packaging"),
        ("приёмк", "inbound"),
        ("приемк", "inbound"),
        ("утилизац", "disposal"),
        ("кросс", "crossdock"),
    )
    for needle, bucket in mapping:
        if needle in name:
            return bucket
    return "other"


def _iter_fees(accrual: dict) -> Iterable[tuple[int | None, float]]:
    """Все удержания начисления: доставка, комиссия, item_fees, non_item_fee."""
    posting = accrual.get("posting") or {}
    for product in posting.get("products") or []:
        commission = product.get("commission") or {}
        sale_commission = _money(commission.get("sale_commission"))
        if sale_commission:
            yield -1, sale_commission  # -1 = комиссия Ozon
        delivery = product.get("delivery") or {}
        for service in delivery.get("services") or []:
            yield to_int(service.get("type_id")), _money(service.get("accrued"))

    for group in (accrual.get("item_fees") or {}).get("fees") or []:
        for fee in group.get("fees") or []:
            yield to_int(fee.get("type_id")), _money(fee.get("accrued"))

    non_item = accrual.get("non_item_fee")
    if non_item:
        yield to_int(non_item.get("type_id")), _money(non_item.get("accrued"))

    containers = accrual.get("container_fees") or []
    for fee in _walk_fees(containers):
        yield to_int(fee.get("type_id")), _money(fee.get("accrued"))


def _walk_fees(node) -> Iterable[dict]:
    if isinstance(node, dict):
        if "type_id" in node and "accrued" in node:
            yield node
            return
        for value in node.values():
            yield from _walk_fees(value)
    elif isinstance(node, list):
        for value in node:
            yield from _walk_fees(value)


def summarize(accruals: list[dict], types: dict[int, str] | None = None) -> dict:
    """Сводит начисления в группы расходов, выручку и разрез по SKU."""
    types = types or {}
    buckets: dict[str, float] = defaultdict(float)
    by_sku: dict[str, dict] = {}
    revenue = 0.0
    payout = 0.0

    for accrual in accruals:
        payout += _money(accrual.get("total_amount"))

        for product in (accrual.get("posting") or {}).get("products") or []:
            sku = str(to_int(product.get("sku")))
            commission = product.get("commission") or {}
            sale_amount = _money(commission.get("sale_amount")) or _money(commission.get("seller_price"))
            revenue += sale_amount
            if sku != "0":
                entry = by_sku.setdefault(sku, {"revenue": 0.0, "fees": 0.0})
                entry["revenue"] += sale_amount

        for type_id, amount in _iter_fees(accrual):
            if type_id == -1:
                key = "commission"
            else:
                key = _bucket_for(types.get(type_id, ""))
            buckets[key] += amount

    # Раскидываем удержания по SKU на уровне начисления
    for accrual in accruals:
        accrual_fees = sum(amount for _, amount in _iter_fees(accrual))
        skus = [
            str(to_int(product.get("sku")))
            for product in (accrual.get("posting") or {}).get("products") or []
        ]
        skus = [sku for sku in skus if sku != "0"]
        if not skus or not accrual_fees:
            continue
        share = accrual_fees / len(skus)
        for sku in skus:
            by_sku.setdefault(sku, {"revenue": 0.0, "fees": 0.0})["fees"] += share

    named = {BUCKETS[key]: round(value, 2) for key, value in buckets.items() if abs(value) > 0.004}

    # Совместимость с блоком дашборда и расчётом маржи
    delivery = (
        buckets.get("logistics", 0.0)
        + buckets.get("last_mile", 0.0)
        + buckets.get("reverse", 0.0)
    )
    services = sum(
        buckets.get(key, 0.0)
        for key in ("advertising", "storage", "acquiring", "packaging", "inbound", "disposal", "crossdock", "other")
    )
    return {
        "source": "accrual",
        "revenue": round(revenue, 2),
        "payout": round(payout, 2),
        "buckets": named,
        "by_sku": {sku: {k: round(v, 2) for k, v in value.items()} for sku, value in by_sku.items()},
        # ключи, которые ожидает остальная часть проекта
        "accruals_for_sale": round(revenue, 2),
        "sale_commission": round(buckets.get("commission", 0.0), 2),
        "processing_and_delivery": round(delivery, 2),
        "refunds_and_cancellations": round(buckets.get("returns", 0.0), 2),
        "services_amount": round(services, 2),
        "compensation_amount": round(buckets.get("compensation", 0.0), 2),
        "money_transfer": 0.0,
        "others_amount": 0.0,
    }


def fetch(client: OzonClient, date_from: date, date_to: date) -> dict:
    """Основной путь: accrual-методы. Бросает OzonAPIError, если недоступны."""
    types = fetch_accrual_types(client)
    accruals = fetch_accruals(client, date_from, date_to)
    summary = summarize(accruals, types)
    summary["accruals_count"] = len(accruals)
    return summary
