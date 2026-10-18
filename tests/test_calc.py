"""Тесты калькулятора прибыли."""

from __future__ import annotations

import unittest

from ozon import calc, calcpage, demo, metrics


def _snapshot(finance: dict | None = None) -> dict:
    return {
        "meta": {"period": {"from": "2025-01-01", "to": "2025-01-30"},
                 "prev_period": {}, "mode": "live", "generated_at": "now"},
        "rows": [{
            "sku": 111, "name": "Розетка", "offer_id": "A-1", "day": "2025-01-10",
            "revenue": 10000, "ordered_units": 10, "returns": 0,
            "session_view": 100, "hits_tocart": 10,
        }],
        "stocks": {}, "turnover": {}, "finance": finance or {},
    }


FINANCE = {
    "accruals_for_sale": 10000,
    "sale_commission": -1500,
    "processing_and_delivery": -500,
    "refunds_and_cancellations": 0,
    "services_amount": -600,
    "compensation_amount": 0,
    "money_transfer": 0,
    "others_amount": 0,
    "buckets": {"Комиссия Ozon": -1500, "Логистика": -500, "Реклама": -500},
}


class ModelTests(unittest.TestCase):
    def test_fee_split_and_ad_rate(self):
        data = metrics.build(_snapshot(FINANCE))
        model = calc.build_model(data)
        self.assertAlmostEqual(model["commission_rate"], 0.15)
        self.assertAlmostEqual(model["ad_rate"], 0.05)
        sku = model["skus"][0]
        self.assertAlmostEqual(sku["price"], 1000)
        self.assertAlmostEqual(sku["fee_fixed"], 0, places=6)
        self.assertAlmostEqual(sku["profit0"], 8000)
        self.assertAlmostEqual(model["totals"]["profit"], 8000)

    def test_cost_is_subtracted(self):
        data = metrics.build(_snapshot(FINANCE))
        model = calc.build_model(data, costs={"111": 300})
        sku = model["skus"][0]
        self.assertAlmostEqual(sku["cost"], 300)
        self.assertAlmostEqual(sku["profit0"], 5000)
        self.assertTrue(model["has_costs"])

    def test_without_finance_uses_gross_revenue(self):
        data = metrics.build(_snapshot())
        model = calc.build_model(data)
        self.assertEqual(model["commission_rate"], 0)
        self.assertEqual(model["ad_rate"], 0)
        sku = model["skus"][0]
        self.assertAlmostEqual(sku["fee_fixed"], 0)
        self.assertAlmostEqual(sku["profit0"], 10000)  # без рекламы и комиссии

    def test_skus_without_sales_are_skipped(self):
        snapshot = _snapshot(FINANCE)
        snapshot["rows"].append({
            "sku": 222, "name": "Без продаж", "day": "2025-01-11",
            "revenue": 0, "ordered_units": 0, "returns": 0,
        })
        model = calc.build_model(metrics.build(snapshot))
        self.assertEqual(len(model["skus"]), 1)


class PageTests(unittest.TestCase):
    def test_render_contains_data_and_controls(self):
        model = calc.build_model(metrics.build(demo.make_snapshot(days=5, seed=3)))
        html_text = calcpage.render(model)
        self.assertIn("Калькулятор прибыли", html_text)
        self.assertIn("window.__SKUS__", html_text)
        self.assertIn("elasticity", html_text)
        self.assertIn("Демонстрационные данные", html_text)
        self.assertNotIn("None", html_text)

    def test_live_page_has_no_demo_banner(self):
        model = calc.build_model(metrics.build(_snapshot(FINANCE)))
        html_text = calcpage.render(model)
        self.assertNotIn("Демонстрационные данные", html_text)
        self.assertIn("live", html_text)


if __name__ == "__main__":
    unittest.main()
