"""Тесты клиента: лимиты методов и пауза перед ретраем."""

from __future__ import annotations

import unittest
from unittest import mock

from ozon import client as client_module
from ozon.client import OzonClient


class RateLimitTests(unittest.TestCase):
    def test_analytics_data_has_minute_interval(self):
        self.assertEqual(client_module.METHOD_INTERVALS["/v1/analytics/data"], 60.0)

    def test_respect_method_limit_sleeps_remaining_time(self):
        slept: list[float] = []
        client = OzonClient("1", "key", sleep=slept.append)
        client._last_by_path["/v1/analytics/data"] = 990.0
        with mock.patch.object(client_module.time, "monotonic", return_value=1000.0):
            client._respect_method_limit("/v1/analytics/data")
        self.assertEqual(len(slept), 1)
        self.assertAlmostEqual(slept[0], 50.0, places=3)

    def test_retry_delay_uses_retry_after_header(self):
        self.assertEqual(OzonClient._retry_delay({"Retry-After": "42"}, 1, 429), 42.0)
        self.assertLessEqual(OzonClient._retry_delay({}, 1, 429), 60.4)
        self.assertGreaterEqual(OzonClient._retry_delay({}, 1, 500), 1.0)


if __name__ == "__main__":
    unittest.main()
