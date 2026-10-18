"""Расчёт метрик: KPI, динамика по дням, юнит-экономика, ABC, алерты."""

from __future__ import annotations

import csv
from pathlib import Path

from .util import safe_div, to_float, to_int

SEVERITY_ORDER = {"red": 0, "yellow": 1, "blue": 2}

FINANCE_LABELS = {
    "accruals_for_sale": "Начислено за продажи",
    "sale_commission": "Комиссия Ozon",
    "processing_and_delivery": "Обработка и доставка",
    "refunds_and_cancellations": "Возвраты и отмены",
    "services_amount": "Доп. услуги",
    "compensation_amount": "Компенсации",
    "money_transfer": "Переводы (rFBS)",
    "others_amount": "Прочее",
}


def load_costs(path: str | Path | None) -> dict[str, float]:
    """CSV с себестоимостью: sku,offer_id,cost (достаточно одного из ключей)."""
    if not path:
        return {}
    path = Path(path)
    if not path.exists():
        return {}
    costs: dict[str, float] = {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if not row:
                continue
            cost = to_float(row.get("cost") or row.get("себестоимость"))
            if cost <= 0:
                continue
            for key in ("sku", "offer_id", "артикул"):
                value = (row.get(key) or "").strip()
                if value:
                    costs[value] = cost
    return costs


def _sum(rows: list[dict], key: str) -> float:
    return sum(to_float(row.get(key)) for row in rows)


def _aggregate(rows: list[dict]) -> dict:
    revenue = _sum(rows, "revenue")
    units = _sum(rows, "ordered_units")
    returns = _sum(rows, "returns")
    sessions = _sum(rows, "session_view")
    tocarts = _sum(rows, "hits_tocart")
    views = _sum(rows, "hits_view")
    return {
        "revenue": revenue,
        "units": units,
        "delivered": _sum(rows, "delivered_units"),
        "returns": returns,
        "cancellations": _sum(rows, "cancellations"),
        "sessions": sessions,
        "tocarts": tocarts,
        "views": views,
        "avg_price": safe_div(revenue, units),
        "return_rate": safe_div(returns, units),
        "cancel_rate": safe_div(_sum(rows, "cancellations"), units),
        "conv": safe_div(tocarts, sessions),
    }


def _finance(snapshot: dict, units: float) -> dict:
    raw = snapshot.get("finance") or {}
    if not raw:
        return {}
    values = {key: to_float(raw.get(key)) for key in FINANCE_LABELS}
    payout = sum(values.values())
    accruals = values.get("accruals_for_sale") or 0.0
    commission_rate = safe_div(-values.get("sale_commission", 0.0), accruals)
    delivery_per_unit = safe_div(-values.get("processing_and_delivery", 0.0), units)
    return {
        "values": values,
        "buckets": raw.get("buckets") or {},
        "payout": payout,
        "commission_rate": commission_rate,
        "delivery_per_unit": delivery_per_unit,
        "has_data": any(abs(v) > 0 for v in values.values()),
    }


def build(snapshot: dict, costs: dict[str, float] | None = None) -> dict:
    costs = costs or {}
    meta = snapshot.get("meta") or {}
    period = meta.get("period") or {}
    prev_period = meta.get("prev_period") or {}
    rows = snapshot.get("rows") or []
    stocks = snapshot.get("stocks") or {}
    turnover = snapshot.get("turnover") or {}

    period_from = str(period.get("from") or "")
    current_rows = [r for r in rows if str(r.get("day")) >= period_from]
    prev_rows = [r for r in rows if str(r.get("day")) < period_from]

    kpi = _aggregate(current_rows)
    prev = _aggregate(prev_rows)

    # --- по дням --------------------------------------------------------
    by_day: dict[str, dict] = {}
    for row in current_rows:
        day = str(row.get("day") or "")
        if not day:
            continue
        acc = by_day.setdefault(day, {"day": day, "revenue": 0.0, "units": 0.0, "returns": 0.0, "sessions": 0.0, "tocarts": 0.0})
        for key in ("revenue", "ordered_units", "returns", "session_view", "hits_tocart"):
            target = {"ordered_units": "units", "session_view": "sessions", "hits_tocart": "tocarts"}.get(key, key)
            acc[target] += to_float(row.get(key))
    daily = []
    for day in sorted(by_day):
        item = by_day[day]
        item["conv"] = safe_div(item["tocarts"], item["sessions"])
        daily.append(item)

    # --- по SKU ---------------------------------------------------------
    finance = _finance(snapshot, kpi["units"])
    commission_rate = finance.get("commission_rate", 0.0) if finance else 0.0
    delivery_per_unit = finance.get("delivery_per_unit", 0.0) if finance else 0.0
    finance_by_sku = ((snapshot.get("finance") or {}).get("by_sku") or {}) if finance else {}

    by_sku: dict[int, dict] = {}
    for row in current_rows:
        sku = to_int(row.get("sku"))
        if not sku:
            continue
        acc = by_sku.setdefault(
            sku,
            {
                "sku": sku,
                "name": row.get("name") or "",
                "revenue": 0.0,
                "units": 0.0,
                "returns": 0.0,
                "cancellations": 0.0,
                "sessions": 0.0,
                "tocarts": 0.0,
                "views": 0.0,
                "prev_revenue": 0.0,
            },
        )
        acc["revenue"] += to_float(row.get("revenue"))
        acc["units"] += to_float(row.get("ordered_units"))
        acc["returns"] += to_float(row.get("returns"))
        acc["cancellations"] += to_float(row.get("cancellations"))
        acc["sessions"] += to_float(row.get("session_view"))
        acc["tocarts"] += to_float(row.get("hits_tocart"))
        acc["views"] += to_float(row.get("hits_view"))
        if not acc["name"] and row.get("name"):
            acc["name"] = row.get("name")

    for row in prev_rows:
        sku = to_int(row.get("sku"))
        if sku in by_sku:
            by_sku[sku]["prev_revenue"] += to_float(row.get("revenue"))

    total_revenue = sum(item["revenue"] for item in by_sku.values())
    sku_rows: list[dict] = []
    for sku, item in by_sku.items():
        stock = stocks.get(str(sku)) or {}
        turn = turnover.get(str(sku)) or {}
        offer_id = stock.get("offer_id") or turn.get("offer_id") or ""
        cost = costs.get(str(sku)) or costs.get(offer_id) or 0.0
        revenue = item["revenue"]
        units = item["units"]
        margin = None
        margin_pct = None
        net_before_cost = None
        settlement = finance_by_sku.get(str(sku))
        if settlement:
            net_before_cost = to_float(settlement.get("revenue")) + to_float(settlement.get("fees"))
        if cost > 0 and finance:
            if net_before_cost is not None:
                margin = net_before_cost - units * cost
            else:
                margin = revenue * (1 - commission_rate) - units * (cost + delivery_per_unit)
            margin_pct = safe_div(margin, revenue)
        sku_rows.append(
            {
                "sku": sku,
                "name": item["name"] or stock.get("name") or turn.get("name") or f"SKU {sku}",
                "offer_id": offer_id,
                "revenue": revenue,
                "units": units,
                "avg_price": safe_div(revenue, units),
                "returns": item["returns"],
                "return_rate": safe_div(item["returns"], units),
                "sessions": item["sessions"],
                "conv": safe_div(item["tocarts"], item["sessions"]),
                "share": safe_div(revenue, total_revenue),
                "prev_revenue": item["prev_revenue"],
                "revenue_delta": safe_div(revenue - item["prev_revenue"], item["prev_revenue"]) if item["prev_revenue"] else None,
                "stock": to_int(stock.get("available")) if stock else to_int(turn.get("current_stock")),
                "idc": to_float(stock.get("idc") if stock else turn.get("idc")),
                "grade": (stock.get("grade") or turn.get("turnover_grade") or "") if (stock or turn) else "",
                "turnover": to_float(turn.get("turnover")),
                "margin": margin,
                "margin_pct": margin_pct,
                "net_before_cost": net_before_cost,
            }
        )

    # --- ABC-анализ -----------------------------------------------------
    sku_rows.sort(key=lambda r: r["revenue"], reverse=True)
    cumulative = 0.0
    for row in sku_rows:
        share_before = safe_div(cumulative, total_revenue)
        cumulative += row["revenue"]
        row["abc"] = "A" if share_before < 0.8 else ("B" if share_before < 0.95 else "C")

    _round_sku_rows(sku_rows)
    alerts = _alerts(sku_rows)

    return {
        "meta": meta,
        "period": period,
        "prev_period": prev_period,
        "kpi": kpi,
        "prev": prev,
        "daily": daily,
        "sku": sku_rows,
        "alerts": alerts,
        "finance": finance,
        "has_funnel": kpi["sessions"] > 0,
        "has_costs": bool(costs),
        "has_settlement": any(row.get("net_before_cost") is not None for row in sku_rows),
    }


def _round_sku_rows(rows: list[dict]) -> None:
    money = ("revenue", "avg_price", "margin", "net_before_cost", "prev_revenue")
    ratios = ("share", "return_rate", "conv", "margin_pct", "revenue_delta")
    for row in rows:
        for key in money:
            if row.get(key) is not None:
                row[key] = round(to_float(row[key]), 2)
        for key in ratios:
            if row.get(key) is not None:
                row[key] = round(to_float(row[key]), 4)
        row["idc"] = round(to_float(row.get("idc")), 1)
        row["units"] = int(round(to_float(row.get("units"))))
        row["sessions"] = int(round(to_float(row.get("sessions"))))
        row["turnover"] = round(to_float(row.get("turnover")), 1)
        row["returns"] = int(round(to_float(row.get("returns"))))
        row["stock"] = int(round(to_float(row.get("stock"))))


def _alerts(sku_rows: list[dict]) -> list[dict]:
    alerts: list[dict] = []
    for row in sku_rows:
        name = row["name"]
        stock = row["stock"]
        idc = row["idc"]
        grade = (row["grade"] or "").upper()

        if stock <= 0 and row["units"] > 0:
            alerts.append(_alert("red", name, row, "Нет в наличии", f"Продано {to_int(row['units'])} шт. за период, остатка нет."))
        elif 0 < idc < 14:
            alerts.append(_alert("red", name, row, f"Хватит на {int(idc)} дн.", "Пора планировать поставку."))

        if grade == "SURPLUS" or idc > 120:
            alerts.append(_alert("yellow", name, row, "Избыток остатка", f"Запаса на {idc:.0f} дн. Риск платного хранения и заморозки денег."))

        if row["return_rate"] >= 0.15 and row["returns"] >= 3:
            alerts.append(
                _alert(
                    "yellow", name, row, "Высокие возвраты",
                    f"возвратов {int(row['returns'])} из {int(row['units'])} шт. ({row['return_rate'] * 100:.0f}%)",
                )
            )

        if row["sessions"] >= 300 and row["conv"] < 0.01:
            alerts.append(_alert("yellow", name, row, "Низкая конверсия в корзину", f"{row['conv'] * 100:.2f}% при {to_int(row['sessions'])} сессиях."))

        delta = row.get("revenue_delta")
        if delta is not None and delta <= -0.3 and row["prev_revenue"] > 0:
            alerts.append(_alert("blue", name, row, f"Выручка {delta * 100:.0f}%", f"Было {to_int(row['prev_revenue'])} ₽, стало {to_int(row['revenue'])} ₽."))

        if grade == "NO_SALES":
            alerts.append(_alert("blue", name, row, "Нет продаж", "Нет продаж последние 28 дней."))

    alerts.sort(key=lambda a: (SEVERITY_ORDER.get(a["level"], 9), -a.get("revenue", 0)))
    return alerts[:60]


def _alert(level: str, name: str, row: dict, title: str, detail: str) -> dict:
    return {
        "level": level,
        "sku": row["sku"],
        "name": name,
        "title": title,
        "detail": detail,
        "revenue": row["revenue"],
    }
