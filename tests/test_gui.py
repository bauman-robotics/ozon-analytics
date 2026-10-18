"""Тесты вспомогательных функций GUI (без запуска окна)."""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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


class BrowserTests(unittest.TestCase):
    def test_open_in_browser_prefers_known_browser(self):
        process = mock.Mock()
        process.wait.side_effect = subprocess.TimeoutExpired("firefox", 0.5)
        which = lambda name: "/usr/bin/firefox" if name == "firefox" else None
        with mock.patch.object(gui.shutil, "which", side_effect=which), \
                mock.patch.object(gui.subprocess, "Popen", return_value=process) as popen:
            gui.open_in_browser(Path("/tmp/dashboard.html"))

        popen.assert_called_once()
        command = popen.call_args.args[0]
        self.assertEqual(command[0], "/usr/bin/firefox")
        self.assertTrue(command[1].startswith("file://"))
        self.assertTrue(command[1].endswith("dashboard.html"))


class DashboardPathTests(unittest.TestCase):
    def test_demo_action_always_opens_demo(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "dashboard.html").write_text("live", encoding="utf-8")
            (folder / "dashboard-demo.html").write_text("demo", encoding="utf-8")
            self.assertEqual(gui.dashboard_path("demo", folder).name, "dashboard-demo.html")

    def test_collect_falls_back_to_demo_only_when_live_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "dashboard-demo.html").write_text("demo", encoding="utf-8")
            self.assertEqual(gui.dashboard_path("collect_all", folder).name, "dashboard-demo.html")
            (folder / "dashboard.html").write_text("live", encoding="utf-8")
            self.assertEqual(gui.dashboard_path("collect_all", folder).name, "dashboard.html")


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
