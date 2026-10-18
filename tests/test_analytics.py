"""Юнит-тесты: парсинг API, метрики, графики, отчёт."""

from __future__ import annotations

import unittest
import xml.etree.ElementTree as ET

from ozon import api, metrics, report, svgchart


class FakeClient:
    def __init__(self, responses: list[dict]):
        self.responses = list(responses)
        self.calls: list[tuple[str, dict]] = []

    def post(self, path: str, payload: dict | None = None, **kwargs) -> dict:
        self.calls.append((path, payload or {}))
        return self.responses.pop(0)


def _row(sku: int, day: str, revenue: float, units: float, returns: float = 0,
         sessions: float = 100, tocarts: float = 10) -> dict:
    return {
        "sku": sku,
        "name": f"Товар {sku}",
        "day": day,
        "revenue": revenue,
        "ordered_units": units,
        "returns": returns,
        "cancellations": 0,
        "session_view": sessions,
        "hits_tocart": tocarts,
    }


class AnalyticsDataTests(unittest.TestCase):
    def test_parses_dimensions_and_metrics(self):
        payload = {
            "result": {
                "data": [
                    {
                        "dimensions": [
                            {"id": "111", "name": "Куртка"},
                            {"id": "2025-01-01", "name": "2025-01-01"},
                        ],
                        "metrics": [1000, 2],
                    }
                ]
            }
        }
        client = FakeClient([payload])
        rows = api.fetch_analytics_data(
            client, __import__("datetime").date(2025, 1, 1), __import__("datetime").date(2025, 1, 1),
            ["revenue", "ordered_units"], ["sku", "day"],
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["sku"], 111)
        self.assertEqual(rows[0]["day"], "2025-01-01")
        self.assertEqual(rows[0]["revenue"], 1000)
        self.assertEqual(rows[0]["name"], "Куртка")

    def test_pagination_requests_next_page(self):
        first = {
            "result": {
                "data": [
                    {"dimensions": [{"id": str(i), "name": ""}, {"id": "2025-01-01", "name": ""}],
                     "metrics": [1]}
                    for i in range(api.PAGE_LIMIT)
                ]
            }
        }
        second = {
            "result": {
                "data": [
                    {"dimensions": [{"id": "999", "name": ""}, {"id": "2025-01-02", "name": ""}],
                     "metrics": [1]}
                ]
            }
        }
        client = FakeClient([first, second])
        rows = api.fetch_analytics_data(
            client, __import__("datetime").date(2025, 1, 1), __import__("datetime").date(2025, 1, 2),
            ["revenue"], ["sku", "day"],
        )
        self.assertEqual(len(rows), api.PAGE_LIMIT + 1)
        self.assertEqual(client.calls[1][1]["offset"], api.PAGE_LIMIT)


class StockTests(unittest.TestCase):
    def test_aggregates_clusters(self):
        payload = {
            "items": [
                {"sku": 111, "name": "Куртка", "offer_id": "A-1", "cluster_name": "Москва",
                 "available_stock_count": 10, "transit_stock_count": 5, "idc": 7.5,
                 "turnover_grade": "DEFICIT"},
                {"sku": 111, "name": "Куртка", "offer_id": "A-1", "cluster_name": "СПб",
                 "available_stock_count": 4, "transit_stock_count": 0, "idc": 7.5,
                 "turnover_grade": "DEFICIT"},
            ]
        }
        client = FakeClient([payload])
        stocks = api.fetch_stocks(client, [111])
        self.assertEqual(stocks[111]["available"], 14)
        self.assertEqual(stocks[111]["transit"], 5)
        self.assertEqual(stocks[111]["idc"], 7.5)
        self.assertEqual(len(stocks[111]["clusters"]), 2)


class MetricsTests(unittest.TestCase):
    def snapshot(self, finance: dict | None = None) -> dict:
        return {
            "meta": {
                "period": {"from": "2025-01-10", "to": "2025-01-11"},
                "prev_period": {"from": "2025-01-08", "to": "2025-01-09"},
                "mode": "demo",
            },
            "rows": [
                _row(111, "2025-01-09", 1000, 2, sessions=80, tocarts=8),
                _row(111, "2025-01-10", 1000, 2, sessions=100, tocarts=10),
                _row(111, "2025-01-11", 500, 1, returns=1, sessions=50, tocarts=5),
            ],
            "stocks": {"111": {"available": 0, "idc": 0, "grade": "DEFICIT"}},
            "turnover": {},
            "finance": finance or {},
        }

    def test_kpi_and_abc(self):
        data = metrics.build(self.snapshot())
        kpi = data["kpi"]
        self.assertAlmostEqual(kpi["revenue"], 1500)
        self.assertAlmostEqual(kpi["units"], 3)
        self.assertAlmostEqual(kpi["return_rate"], 1 / 3)
        self.assertAlmostEqual(kpi["conv"], 15 / 150)
        self.assertEqual(data["sku"][0]["abc"], "A")
        self.assertAlmostEqual(data["sku"][0]["revenue_delta"], 0.5)

    def test_alert_for_out_of_stock(self):
        data = metrics.build(self.snapshot())
        titles = [a["title"] for a in data["alerts"]]
        self.assertIn("Нет в наличии", titles)

    def test_margin_estimate_with_costs(self):
        finance = {
            "accruals_for_sale": 1500,
            "sale_commission": -225,
            "processing_and_delivery": -180,
            "refunds_and_cancellations": -50,
            "services_amount": -30,
            "compensation_amount": 0,
            "money_transfer": 0,
            "others_amount": 0,
        }
        data = metrics.build(self.snapshot(finance), costs={"111": 300})
        row = data["sku"][0]
        self.assertAlmostEqual(row["margin"], 195, places=4)
        self.assertAlmostEqual(data["finance"]["commission_rate"], 0.15)
        self.assertAlmostEqual(data["finance"]["delivery_per_unit"], 60)
        self.assertAlmostEqual(data["finance"]["payout"], 1015)


class ChartTests(unittest.TestCase):
    def test_line_chart_is_valid_svg(self):
        svg = svgchart.line_chart([("2025-01-01", 10), ("2025-01-02", 30)])
        ET.fromstring(svg)

    def test_empty_chart_placeholder(self):
        svg = svgchart.line_chart([])
        ET.fromstring(svg)
        self.assertIn("нет данных", svg)

    def test_bar_and_funnel(self):
        ET.fromstring(svgchart.bar_chart_h([("Товар", 100)]))
        ET.fromstring(svgchart.funnel([("Сессии", 100), ("Заказы", 5)]))


class ReportTests(unittest.TestCase):
    def test_render_full(self):
        from ozon import demo

        snapshot = demo.make_snapshot(days=5, seed=7)
        data = metrics.build(snapshot, costs={"100000": 500})
        html_text = report.render(data)
        self.assertIn("Аналитика Ozon", html_text)
        self.assertIn("<svg", html_text)
        self.assertIn("sku-table", html_text)
        self.assertNotIn("None", html_text)
        self.assertIn("демонстрационные данные", html_text)

    def test_render_without_finance(self):
        snapshot = {
            "meta": {"period": {"from": "2025-01-01", "to": "2025-01-02"},
                     "prev_period": {}, "mode": "live", "generated_at": "now"},
            "rows": [_row(1, "2025-01-01", 100, 1)],
            "stocks": {},
            "turnover": {},
            "finance": {},
        }
        html_text = report.render(metrics.build(snapshot))
        self.assertIn("Аналитика Ozon", html_text)
        self.assertNotIn("None", html_text)
        self.assertNotIn("демонстрационные данные", html_text)


if __name__ == "__main__":
    unittest.main()


class FinanceAccrualTests(unittest.TestCase):
    def _accruals(self):
        return [
            {
                "accrual_id": 1,
                "date": "2025-01-10",
                "total_amount": {"amount": "1000.00", "currency": "RUB"},
                "posting": {
                    "products": [
                        {
                            "sku": 111,
                            "commission": {
                                "sale_amount": {"amount": "1000"},
                                "sale_commission": {"amount": "-150"},
                            },
                            "delivery": {"services": [{"type_id": 2, "accrued": {"amount": "-60"}}]},
                        }
                    ]
                },
            },
            {
                "accrual_id": 2,
                "date": "2025-01-10",
                "total_amount": {"amount": "-50"},
                "posting": {"products": [{"sku": 111, "commission": {"sale_amount": {"amount": "0"}}}]},
                "non_item_fee": {"type_id": 5, "accrued": {"amount": "-50"}},
            },
            {
                "accrual_id": 3,
                "date": "2025-01-11",
                "total_amount": {"amount": "100"},
                "container_fees": [{"type_id": 9, "accrued": {"amount": "100"}}],
            },
        ]

    def test_buckets_and_payout(self):
        from ozon import finance

        types = {2: "Логистика", 5: "Хранение", 7: "Обратная логистика", 9: "Компенсации"}
        summary = finance.summarize(self._accruals(), types)
        self.assertAlmostEqual(summary["revenue"], 1000)
        self.assertAlmostEqual(summary["payout"], 1050)
        self.assertAlmostEqual(summary["buckets"]["Комиссия Ozon"], -150)
        self.assertAlmostEqual(summary["buckets"]["Логистика"], -60)
        self.assertAlmostEqual(summary["buckets"]["Хранение"], -50)
        self.assertAlmostEqual(summary["buckets"]["Компенсации"], 100)
        self.assertAlmostEqual(summary["sale_commission"], -150)
        self.assertAlmostEqual(summary["processing_and_delivery"], -60)
        self.assertAlmostEqual(summary["services_amount"], -50)

    def test_by_sku_net(self):
        from ozon import finance

        types = {2: "Логистика", 5: "Хранение", 9: "Компенсации"}
        summary = finance.summarize(self._accruals(), types)
        self.assertAlmostEqual(summary["by_sku"]["111"]["revenue"], 1000)
        self.assertAlmostEqual(summary["by_sku"]["111"]["fees"], -260)

    def test_margin_uses_actual_settlement(self):
        from ozon import finance

        summary = finance.summarize(self._accruals(), {2: "Логистика", 5: "Хранение", 9: "Компенсации"})
        snapshot = {
            "meta": {"period": {"from": "2025-01-10", "to": "2025-01-11"}, "prev_period": {}},
            "rows": [_row(111, "2025-01-10", 1000, 2), _row(111, "2025-01-11", 0, 1)],
            "stocks": {},
            "turnover": {},
            "finance": summary,
        }
        data = metrics.build(snapshot, costs={"111": 200})
        row = data["sku"][0]
        self.assertAlmostEqual(row["net_before_cost"], 740)
        self.assertAlmostEqual(row["margin"], 140)  # 740 - 3 * 200


class NoFunnelDisplayTests(unittest.TestCase):
    def test_dashes_instead_of_zero_conversion(self):
        snapshot = {
            "meta": {"period": {"from": "2025-01-01", "to": "2025-01-02"},
                     "prev_period": {}, "mode": "live",
                     "generated_at": "now"},
            "rows": [_row(1, "2025-01-01", 100, 2, sessions=0, tocarts=0)],
            "stocks": {},
            "turnover": {},
            "finance": {},
        }
        html_text = report.render(metrics.build(snapshot))
        self.assertIn("Нет данных по сессиям", html_text)
        self.assertGreaterEqual(html_text.count("—</td>"), 2)
