"""Демо-данные: позволяют посмотреть дашборд без ключа API."""

from __future__ import annotations

import random
from datetime import timedelta

from .util import iso_day, utc_now_iso, utc_today

NAMES = [
    "Куртка зимняя женская с капюшоном",
    "Термобелье мужское комплект",
    "Ботинки треккинговые водонепроницаемые",
    "Рюкзак городской 20 л",
    "Перчатки сенсорные зимние",
    "Шапка вязаная с помпоном",
    "Носки треккинговые 3 пары",
    "Дождевик компактный",
    "Спортивный костюм женский",
    "Леггинсы для йоги",
    "Футболка оверсайз хлопок",
    "Худи на флисе",
    "Кроссовки беговые",
    "Сандалии летние",
    "Коврик для йоги 6 мм",
    "Бутылка для воды 750 мл",
    "Термос 500 мл",
    "Ланчбокс с секциями",
    "Органайзер для белья",
    "Вешалки набор 10 шт",
    "Подушка ортопедическая",
    "Плед флисовый 150×200",
    "Ночник LED с таймером",
    "Кружка керамическая 350 мл",
]



def make_snapshot(days: int = 30, seed: int = 42) -> dict:
    rng = random.Random(seed)
    today = utc_today()
    period_to = today
    period_from = today - timedelta(days=days - 1)
    prev_to = period_from - timedelta(days=1)
    prev_from = prev_to - timedelta(days=days - 1)
    start = prev_from

    skus = []
    for index, name in enumerate(NAMES):
        sku = 100000 + index * 137
        price = round(rng.uniform(450, 6500), -1)
        base_units = rng.uniform(0.4, 7.0)
        trend = rng.uniform(-0.35, 0.55)
        return_rate = rng.uniform(0.02, 0.22)
        stock = rng.choice([0, 4, 12, 35, 90, 260, 640])
        grade = "DEFICIT"
        skus.append(
            {
                "sku": sku,
                "name": name,
                "offer_id": f"ART-{1000 + index}",
                "price": price,
                "base": base_units,
                "trend": trend,
                "return_rate": return_rate,
                "stock": stock,
                "grade": grade,
            }
        )

    rows: list[dict] = []
    total_days = (period_to - start).days + 1
    for item in skus:
        for offset in range(total_days):
            day = start + timedelta(days=offset)
            day_index = offset
            weekday_factor = 1.18 if day.weekday() >= 5 else 0.96
            trend_factor = 1 + item["trend"] * day_index / max(total_days, 1)
            units = max(0.0, item["base"] * weekday_factor * trend_factor * rng.uniform(0.55, 1.5))
            units = round(units)
            sessions = int(units * rng.uniform(18, 45)) + rng.randint(0, 40)
            tocarts = int(sessions * rng.uniform(0.03, 0.11))
            returns = round(units * item["return_rate"] * rng.uniform(0.4, 1.5))
            revenue = units * item["price"] * rng.uniform(0.98, 1.0)
            rows.append(
                {
                    "sku": item["sku"],
                    "name": item["name"],
                    "day": iso_day(day),
                    "revenue": round(revenue, 2),
                    "ordered_units": units,
                    "delivered_units": max(0, units - returns),
                    "returns": returns,
                    "cancellations": 0 if rng.random() > 0.06 else 1,
                    "session_view": sessions,
                    "hits_view": int(sessions * rng.uniform(1.3, 2.2)),
                    "hits_tocart": tocarts,
                    "conv_tocart": round(tocarts / sessions, 4) if sessions else 0,
                }
            )

    current = [r for r in rows if r["day"] >= iso_day(period_from)]
    revenue = sum(r["revenue"] for r in current)
    units = sum(r["ordered_units"] for r in current)
    returns = sum(r["returns"] for r in current)

    stocks = {}
    for item in skus:
        ads = item["base"] * 1.05
        idc = (item["stock"] / ads) if ads else 0
        if item["stock"] <= 0:
            item["grade"] = "DEFICIT"
        elif idc < 28:
            item["grade"] = "DEFICIT"
        elif idc < 56:
            item["grade"] = "POPULAR"
        elif idc <= 120:
            item["grade"] = "ACTUAL"
        else:
            item["grade"] = "SURPLUS"
        stocks[str(item["sku"])] = {
            "sku": item["sku"],
            "name": item["name"],
            "offer_id": item["offer_id"],
            "available": item["stock"],
            "valid": 0,
            "transit": rng.choice([0, 0, 40, 120]),
            "requested": 0,
            "return_from_customer": 0,
            "defect": 0,
            "expiring": 0,
            "idc": round(idc, 1),
            "grade": item["grade"],
            "clusters": [
                {"cluster": "Москва, МО и Дальние регионы", "available": int(item["stock"] * 0.6), "idc": round(idc * 0.6, 1), "grade": item["grade"]},
                {"cluster": "Санкт-Петербург и СЗО", "available": int(item["stock"] * 0.25), "idc": round(idc * 0.25, 1), "grade": item["grade"]},
                {"cluster": "Юг", "available": int(item["stock"] * 0.15), "idc": round(idc * 0.15, 1), "grade": item["grade"]},
            ],
        }

    by_sku = {}
    for item in skus:
        sku_rows = [r for r in current if r["sku"] == item["sku"]]
        sku_revenue = sum(r["revenue"] for r in sku_rows)
        sku_units = sum(r["ordered_units"] for r in sku_rows)
        sku_returns = sum(r["returns"] for r in sku_rows)
        by_sku[str(item["sku"])] = {
            "revenue": round(sku_revenue, 2),
            "fees": round(-sku_revenue * 0.155 - sku_units * 62.0 - sku_returns * 180.0, 2),
        }

    finance = {
        "source": "accrual",
        "by_sku": by_sku,
        "accruals_for_sale": round(revenue, 2),
        "sale_commission": round(-revenue * 0.155, 2),
        "processing_and_delivery": round(-units * 62.0, 2),
        "refunds_and_cancellations": round(-returns * 180.0, 2),
        "services_amount": round(-revenue * 0.021, 2),
        "compensation_amount": round(revenue * 0.004, 2),
        "money_transfer": 0.0,
        "others_amount": round(revenue * 0.001, 2),
        "buckets": {
            "Комиссия Ozon": round(-revenue * 0.155, 2),
            "Логистика": round(-units * 62.0 * 0.75, 2),
            "Последняя миля": round(-units * 62.0 * 0.25, 2),
            "Реклама": round(-revenue * 0.012, 2),
            "Хранение": round(-revenue * 0.005, 2),
            "Эквайринг": round(-revenue * 0.004, 2),
            "Возвраты и отмены": round(-returns * 180.0, 2),
            "Компенсации": round(revenue * 0.004, 2),
        },
    }

    turnover = {
        str(item["sku"]): {
            "sku": item["sku"],
            "name": item["name"],
            "offer_id": item["offer_id"],
            "ads": round(item["base"], 2),
            "current_stock": item["stock"],
            "idc": round(stocks[str(item["sku"])]["idc"], 1),
            "idc_grade": "GRADES_GREEN" if item["stock"] else "GRADES_CRITICAL",
            "turnover": round(item["stock"] / (item["base"] or 1), 1),
            "turnover_grade": item["grade"],
        }
        for item in skus
    }

    return {
        "meta": {
            "generated_at": utc_now_iso(),
            "mode": "demo",
            "client_id_masked": "demo",
            "days": days,
            "period": {"from": iso_day(period_from), "to": iso_day(period_to)},
            "prev_period": {"from": iso_day(prev_from), "to": iso_day(prev_to)},
            "api_calls": 0,
            "warnings": [],
        },
        "rows": rows,
        "stocks": stocks,
        "turnover": turnover,
        "finance": finance,
    }
