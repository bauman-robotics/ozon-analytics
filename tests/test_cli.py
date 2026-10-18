"""Регрессионные тесты CLI: команды не должны падать на отсутствии настроек."""

from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout
from unittest import mock

import run as cli
from ozon.config import Settings


class CliTests(unittest.TestCase):
    def test_all_command_has_no_report_flag_but_works(self):
        """`all` не объявляет --report, но cmd_collect не должен из-за этого падать."""
        args = cli.build_parser().parse_args(["all", "--days", "1"])
        self.assertFalse(hasattr(args, "report"))
        with mock.patch.object(cli.Settings, "from_env", return_value=Settings()), \
                redirect_stdout(io.StringIO()):
            code = args.func(args)
        self.assertEqual(code, 2)          # нет ключа → код 2, без исключения
        self.assertTrue(args.report)       # cmd_all сам включает сборку отчёта

    def test_collect_without_report_flag(self):
        args = cli.build_parser().parse_args(["collect", "--days", "1"])
        with mock.patch.object(cli.Settings, "from_env", return_value=Settings()), \
                redirect_stdout(io.StringIO()):
            self.assertEqual(args.func(args), 2)

    def test_check_offline_reports_missing_env(self, tmp_path=None):
        args = cli.build_parser().parse_args(["check", "--offline"])
        with mock.patch.object(cli.Settings, "from_env", return_value=Settings()), \
                redirect_stdout(io.StringIO()):
            self.assertEqual(args.func(args), 2)


if __name__ == "__main__":
    unittest.main()
