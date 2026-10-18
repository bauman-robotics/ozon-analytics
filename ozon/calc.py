"""Модель калькулятора прибыли: разбор издержек на единицу и база для сценариев."""

from __future__ import annotations

from .util import safe_div, to_float, to_int


def build_model(data: dict, costs: dict[str, float] | None = None) -> dict:
    """Готовит данные для страницы-калькулятора.

    Для каждого SKU разделяет издержки Ozon на:
      • процент от цены (комиссия) — меняется вместе с ценой;
      • фиксированную часть на единицу (логистика, последняя миля, хранение и т.п.).
    Реклама выносится в отдельный параметр, чтобы её можно было крутить.
    """
    costs = costs or {}
    rows = data.get("sku") or []
    finance = data.get("finance") or {}
    commission_rate = to_float(finance.get("commission_rate")) if finance else 0.0
    delivery_per_unit = to_float(finance.get("delivery_per_unit")) if finance else 0.0
    buckets = finance.get("buckets") or {}

    revenue_total = sum(to_float(r.get("revenue")) for r in rows)
    ad_total = max(0.0, -to_float(buckets.get("Реклама")))
    ad_rate = min(1.0, safe_div(ad_total, revenue_total)) if revenue_total else 0.0

    skus: list[dict] = []
    for row in rows:
        units = to_float(row.get("units"))
        revenue = to_float(row.get("revenue"))
        if units <= 0 or revenue <= 0:
            continue
        price = revenue / units
        net = row.get("net_before_cost")
        if net is None:
            net = revenue * (1 - commission_rate) - units * delivery_per_unit
        net = to_float(net)
        net_ex_ads = net + revenue * ad_rate

        fee_total = revenue - net_ex_ads
        fee_fixed = fee_total / units - price * commission_rate
        cost = costs.get(str(row.get("sku"))) or costs.get(str(row.get("offer_id") or "")) or 0.0

        skus.append(
            {
                "sku": to_int(row.get("sku")),
                "name": row.get("name") or f"SKU {row.get('sku')}",
                "offer_id": row.get("offer_id") or "",
                "price": round(price, 2),
                "units": int(round(units)),
                "commission": round(commission_rate, 4),
                "fee_fixed": round(fee_fixed, 2),
                "cost": round(to_float(cost), 2),
                "has_cost": to_float(cost) > 0,
                "profit0": round(net_ex_ads - revenue * ad_rate - units * to_float(cost), 2),
                "revenue": round(revenue, 2),
            }
        )

    skus.sort(key=lambda item: item["revenue"], reverse=True)
    profit_total = sum(item["profit0"] for item in skus)
    units_total = sum(item["units"] for item in skus)

    return {
        "meta": data.get("meta") or {},
        "period": data.get("period") or {},
        "commission_rate": round(commission_rate, 4),
        "ad_rate": round(ad_rate, 4),
        "has_costs": any(item["has_cost"] for item in skus),
        "totals": {
            "revenue": round(revenue_total, 2),
            "units": int(round(units_total)),
            "profit": round(profit_total, 2),
            "avg_price": round(safe_div(revenue_total, units_total), 2),
        },
        "skus": skus,
    }
