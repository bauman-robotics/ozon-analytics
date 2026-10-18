"""Методы Seller API, нормализованные в простые структуры."""

from __future__ import annotations

from datetime import date
from typing import Any

from .client import OzonAPIError, OzonClient
from .util import api_datetime, iso_day, to_float, to_int

SALES_METRICS = ["revenue", "ordered_units", "delivered_units", "returns", "cancellations"]

# Лимит Ozon — не более 14 метрик в одном запросе.
# Только те метрики, которые реально нужны дашборду.
# Часть «search/pdp»-метрик Ozon помечает как deprecated и отклоняет весь запрос,
# поэтому их не запрашиваем.
FUNNEL_METRICS = ["session_view", "hits_tocart", "hits_view"]
FUNNEL_FALLBACK = ["session_view"]

PAGE_LIMIT = 1000


def fetch_roles(client: OzonClient, *, attempts: int = 4) -> dict:
    """Роли, методы и срок действия ключа (POST /v1/roles)."""
    return client.post("/v1/roles", {}, attempts=attempts)


def fetch_seller_info(client: OzonClient) -> dict:
    try:
        return client.post("/v1/seller/info", {})
    except OzonAPIError as exc:
        return {"error": str(exc)}


def fetch_analytics_data(
    client: OzonClient,
    date_from: date,
    date_to: date,
    metrics: list[str],
    dimension: list[str],
    *,
    max_pages: int = 100,
) -> list[dict]:
    """POST /v1/analytics/data с пагинацией. Возвращает плоские строки."""
    rows: list[dict] = []
    offset = 0
    truncated = True
    for _ in range(max_pages):
        payload = {
            "date_from": iso_day(date_from),
            "date_to": iso_day(date_to),
            "metrics": metrics,
            "dimension": dimension,
            "filters": [],
            "limit": PAGE_LIMIT,
            "offset": offset,
        }
        response = client.post("/v1/analytics/data", payload)
        result = response.get("result") or {}
        data = result.get("data") or []
        for item in data:
            dims = item.get("dimensions") or []
            values = item.get("metrics") or []
            row: dict[str, Any] = {}
            for index, key in enumerate(dimension):
                if index >= len(dims):
                    continue
                dim = dims[index] or {}
                raw_id = dim.get("id")
                row[key] = raw_id
                if key == "sku":
                    row["sku"] = to_int(raw_id)
                    name = (dim.get("name") or "").strip()
                    if name and name != str(raw_id):
                        row.setdefault("name", name)
            for index, key in enumerate(metrics):
                if index < len(values):
                    row[key] = values[index]
            rows.append(row)
        if len(data) < PAGE_LIMIT:
            truncated = False
            break
        offset += PAGE_LIMIT
    if truncated:
        client.warnings.append(
            f"Данные /v1/analytics/data обрезаны на {max_pages * PAGE_LIMIT} строках — "
            "увеличьте max_pages или уменьшите период"
        )
    return rows


def fetch_stocks(client: OzonClient, skus: list[int], *, chunk: int = 100) -> dict[int, dict]:
    """POST /v1/analytics/stocks — остатки по кластерам, агрегируем до SKU."""
    aggregated: dict[int, dict] = {}
    unique = [str(s) for s in dict.fromkeys(skus) if s]
    for start in range(0, len(unique), chunk):
        part = unique[start : start + chunk]
        response = client.post("/v1/analytics/stocks", {"skus": part})
        for item in response.get("items") or []:
            sku = to_int(item.get("sku"))
            if not sku:
                continue
            acc = aggregated.setdefault(
                sku,
                {
                    "sku": sku,
                    "name": item.get("name") or "",
                    "offer_id": item.get("offer_id") or "",
                    "available": 0,
                    "valid": 0,
                    "transit": 0,
                    "requested": 0,
                    "return_from_customer": 0,
                    "defect": 0,
                    "expiring": 0,
                    "idc": None,
                    "grade": None,
                    "clusters": [],
                },
            )
            acc["available"] += to_int(item.get("available_stock_count"))
            acc["valid"] += to_int(item.get("valid_stock_count"))
            acc["transit"] += to_int(item.get("transit_stock_count"))
            acc["requested"] += to_int(item.get("requested_stock_count"))
            acc["return_from_customer"] += to_int(item.get("return_from_customer_stock_count"))
            acc["defect"] += to_int(item.get("stock_defect_stock_count"))
            acc["expiring"] += to_int(item.get("expiring_stock_count"))
            if acc["idc"] is None and item.get("idc") is not None:
                acc["idc"] = to_float(item.get("idc"))
            if not acc["grade"]:
                acc["grade"] = item.get("turnover_grade")
            acc["clusters"].append(
                {
                    "cluster": item.get("cluster_name") or "",
                    "available": to_int(item.get("available_stock_count")),
                    "idc": to_float(item.get("idc_cluster")),
                    "grade": item.get("turnover_grade_cluster"),
                }
            )
    return aggregated


def fetch_turnover(client: OzonClient, *, max_pages: int = 1, page_limit: int = 1000) -> dict[int, dict]:
    """POST /v1/analytics/turnover/stocks — оборачиваемость (лимит 1 запрос/мин)."""
    items: dict[int, dict] = {}
    offset = 0
    for _ in range(max_pages):
        response = client.post(
            "/v1/analytics/turnover/stocks",
            {"limit": page_limit, "offset": offset},
        )
        chunk = response.get("items") or []
        for item in chunk:
            sku = to_int(item.get("sku"))
            if sku:
                items[sku] = {
                    "sku": sku,
                    "name": item.get("name") or "",
                    "offer_id": item.get("offer_id") or "",
                    "ads": to_float(item.get("ads")),
                    "current_stock": to_int(item.get("current_stock")),
                    "idc": to_float(item.get("idc")),
                    "idc_grade": item.get("idc_grade"),
                    "turnover": to_float(item.get("turnover")),
                    "turnover_grade": item.get("turnover_grade"),
                }
        if len(chunk) < page_limit:
            break
        offset += page_limit
    return items


def fetch_finance_totals(client: OzonClient, date_from: date, date_to: date) -> dict:
    """POST /v3/finance/transaction/totals — итоговые суммы за период."""
    payload = {
        "date": {
            "from": api_datetime(date_from),
            "to": api_datetime(date_to, end_of_day=True),
        },
        "posting_number": "",
        "transaction_type": "all",
    }
    response = client.post("/v3/finance/transaction/totals", payload)
    result = response.get("result") or {}
    keys = [
        "accruals_for_sale",
        "sale_commission",
        "processing_and_delivery",
        "refunds_and_cancellations",
        "services_amount",
        "compensation_amount",
        "money_transfer",
        "others_amount",
    ]
    return {key: to_float(result.get(key)) for key in keys}


def fetch_realization(client: OzonClient, year: int, month: int) -> list[dict]:
    """POST /v2/finance/realization — отчёт о реализации за месяц (по SKU)."""
    response = client.post("/v2/finance/realization", {"year": year, "month": month})
    result = response.get("result") or {}
    return result.get("rows") or []
