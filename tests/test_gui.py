"""Тесты вспомогательных функций GUI (без запуска окна)."""

from __future__ import annotations

import unittest
from pathlib import Path

import gui
from ozon.config import Settings


class CommandTests(unittest.TestCase):
    def test_collect_all_command(self):
        cmd = gui.build_command("collect_all", 14)
        self.assertIn("all", cmd)
        self.assertIn("14", cmd)
        self.assertTrue(cmd[2].endswith("run.py"))
        self.assertNotIn("--include-today", cmd)

    def test_include_today_flag(self):
        cmd = gui.build_command("collect_all", 7, include_today=True)
        self.assertIn("--include-today", cmd)

    def test_simple_actions(self):
        for action in ("report", "calc", "demo", "check"):
            cmd = gui.build_command(action)
            self.assertEqual(cmd[-1], action)

    def test_unknown_action_raises(self):
        with self.assertRaises(ValueError):
            gui.build_command("nope")

    def test_python_is_not_windowed(self):
        exe = Path(gui.python_exe())
        self.assertNotIn(exe.name.lower(), {"pythonw.exe", "pythonw"})


class StatusTests(unittest.TestCase):
    def test_missing_key_message(self):
        text = gui.status_text(Settings(), Path("/nonexistent/.env"))
        self.assertIn("Ключ не настроен", text)

    def test_configured_status_masks_client_id(self):
        settings = Settings(client_id="1234567", api_key="secret")
        text = gui.status_text(settings)
        self.assertIn("…4567", text)
        self.assertNotIn("1234567", text)
        self.assertNotIn("secret", text)


if __name__ == "__main__":
    unittest.main()
