"""Тесты сборщика: границы периода."""

from __future__ import annotations

import unittest
from datetime import date, timedelta
from unittest import mock

from ozon import collect as collector
from ozon.config import Settings


class FakeClient:
    def __init__(self, *args, **kwargs):
        self.calls = 0
        self.warnings: list[str] = []

    def post(self, path, payload=None, **kwargs):
        return {"result": {"data": []}, "items": [], "accruals": [], "last_id": ""}


class CollectPeriodTests(unittest.TestCase):
    def _collect(self, **kwargs):
        with mock.patch.object(collector, "OzonClient", FakeClient), \
                mock.patch.object(collector.finance_api, "fetch", return_value={}), \
                mock.patch.object(collector.api, "fetch_stocks", return_value={}), \
                mock.patch.object(collector.api, "fetch_turnover", return_value={}):
            settings = Settings(client_id="1", api_key="k")
            return collector.collect(settings, days=7, log=lambda *_: None, **kwargs)

    def test_period_ends_yesterday_by_default(self):
        snapshot = self._collect()
        expected = (date.today() - timedelta(days=1)).isoformat()
        self.assertEqual(snapshot["meta"]["period"]["to"], expected)

    def test_include_today_flag(self):
        snapshot = self._collect(include_today=True)
        self.assertEqual(snapshot["meta"]["period"]["to"], date.today().isoformat())

    def test_period_length(self):
        snapshot = self._collect()
        start = date.fromisoformat(snapshot["meta"]["period"]["from"])
        end = date.fromisoformat(snapshot["meta"]["period"]["to"])
        self.assertEqual((end - start).days + 1, 7)


if __name__ == "__main__":
    unittest.main()
