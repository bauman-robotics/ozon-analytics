"""Тесты сборщика: границы периода."""

from __future__ import annotations

import unittest
from datetime import date, timedelta
from unittest import mock

from ozon import api
from ozon import collect as collector
from ozon.client import OzonAPIError
from ozon.config import Settings
from ozon.util import utc_today


class FakeClient:
    instances: list["FakeClient"] = []

    def __init__(self, *args, **kwargs):
        self.calls = 0
        self.warnings: list[str] = []
        self.requests: list[tuple[str, dict]] = []
        FakeClient.instances.append(self)

    def post(self, path, payload=None, **kwargs):
        self.requests.append((path, payload or {}))
        return {"result": {"data": []}, "items": [], "accruals": [], "last_id": ""}


class RejectExtendedMetricsClient(FakeClient):
    """Первый запрос с расширенным набором метрик Ozon отклоняет."""

    def post(self, path, payload=None, **kwargs):
        if path == "/v1/analytics/data" and payload.get("metrics") == api.SALES_METRICS:
            self.requests.append((path, payload or {}))
            raise OzonAPIError(
                "Ошибка Ozon API (HTTP 400): deprecated metrics used",
                status=400,
                body='{"code": 3, "message": "deprecated metrics used"}',
            )
        return super().post(path, payload, **kwargs)


class CollectPeriodTests(unittest.TestCase):
    def _collect(self, client_cls=FakeClient, **kwargs):
        FakeClient.instances = []
        with mock.patch.object(collector, "OzonClient", client_cls), \
                mock.patch.object(collector.finance_api, "fetch", return_value={}), \
                mock.patch.object(collector.api, "fetch_stocks", return_value={}), \
                mock.patch.object(collector.api, "fetch_turnover", return_value={}):
            settings = Settings(client_id="1", api_key="k")
            return collector.collect(settings, days=7, log=lambda *_: None, **kwargs)

    def test_period_ends_yesterday_by_default(self):
        snapshot = self._collect()
        expected = (utc_today() - timedelta(days=1)).isoformat()
        self.assertEqual(snapshot["meta"]["period"]["to"], expected)

    def test_include_today_flag(self):
        snapshot = self._collect(include_today=True)
        self.assertEqual(snapshot["meta"]["period"]["to"], utc_today().isoformat())

    def test_period_length(self):
        snapshot = self._collect()
        start = date.fromisoformat(snapshot["meta"]["period"]["from"])
        end = date.fromisoformat(snapshot["meta"]["period"]["to"])
        self.assertEqual((end - start).days + 1, 7)

    def test_deprecated_funnel_metrics_are_not_requested(self):
        self._collect()
        client = FakeClient.instances[-1]
        payloads = [payload for path, payload in client.requests if path == "/v1/analytics/data"]
        self.assertEqual(len(payloads), 1)
        self.assertEqual(payloads[0]["metrics"], api.SALES_METRICS)

    def test_sales_fallback_after_400(self):
        snapshot = self._collect(client_cls=RejectExtendedMetricsClient)
        client = RejectExtendedMetricsClient.instances[-1]
        payloads = [payload for path, payload in client.requests if path == "/v1/analytics/data"]
        self.assertEqual(len(payloads), 2)
        self.assertEqual(payloads[0]["metrics"], api.SALES_METRICS)
        self.assertEqual(payloads[1]["metrics"], api.SALES_FALLBACK_METRICS)
        warnings = snapshot["meta"]["warnings"]
        self.assertTrue(any("только выручка и заказы" in warning for warning in warnings))


if __name__ == "__main__":
    unittest.main()
