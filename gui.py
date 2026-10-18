#!/usr/bin/env python3
"""Простой графический интерфейс для Windows (Tkinter, без зависимостей).

Запуск: двойной клик по run_gui.bat или `pyw gui.py`.
Интерфейс ничего не считает — он запускает команды run.py и показывает лог.
Тёмная тема по умолчанию, переключатель — в правом верхнем углу.
"""

from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ozon.config import DEFAULT_ENV, Settings  # noqa: E402

OUT_DIR = ROOT / "out"
DATA_DIR = ROOT / "data"
PREFS_FILE = DATA_DIR / "gui_prefs.json"
CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0

THEMES = {
    "dark": {
        "bg": "#0f1420", "card": "#161d2c", "panel": "#121927", "border": "#2a3448",
        "text": "#e6ebf5", "muted": "#8b95ab", "accent": "#5ea0ff", "accent_hover": "#7bb4ff",
        "input": "#0d1320", "button": "#1b2436", "button_hover": "#243049",
        "log_bg": "#0b101b", "log_fg": "#d7deea", "select": "#26324a",
        "error": "#f87171", "ok": "#34d399", "cmd": "#7bb4ff",
    },
    "light": {
        "bg": "#f1f3f8", "card": "#ffffff", "panel": "#f1f3f8", "border": "#dfe3ec",
        "text": "#121826", "muted": "#6b7280", "accent": "#2563eb", "accent_hover": "#1d4ed8",
        "input": "#ffffff", "button": "#ffffff", "button_hover": "#eef2fb",
        "log_bg": "#ffffff", "log_fg": "#121826", "select": "#dbeafe",
        "error": "#b91c1c", "ok": "#047857", "cmd": "#1d4ed8",
    },
}

ACTIONS = {
    "collect_all": "Собрать и открыть дашборд",
    "report": "Пересобрать отчёт",
    "calc": "Калькулятор прибыли",
    "demo": "Демо-дашборд",
    "check": "Проверить ключ",
}


# --------------------------------------------------------------------------
# Вспомогательные функции (без Tkinter — тестируются отдельно)
# --------------------------------------------------------------------------
def python_exe() -> str:
    """python.exe, а не pythonw.exe: нужно получать вывод команды."""
    exe = Path(sys.executable)
    if exe.name.lower() in ("pythonw.exe", "pythonw"):
        candidate = exe.with_name("python.exe")
        if candidate.exists():
            return str(candidate)
    return str(exe)


def build_command(action: str, days: int = 30, include_today: bool = False) -> list[str]:
    base = [python_exe(), "-u", str(ROOT / "run.py")]
    if action == "collect_all":
        cmd = base + ["all", "--days", str(int(days))]
        if include_today:
            cmd.append("--include-today")
        return cmd
    if action in ("report", "calc", "demo", "check"):
        return base + [action]
    raise ValueError(f"неизвестное действие: {action}")


def mask(value: str, keep: int = 4) -> str:
    value = (value or "").strip()
    if not value:
        return "—"
    return value if len(value) <= keep else "…" + value[-keep:]


def status_text(settings: Settings, env_path: Path = DEFAULT_ENV) -> str:
    if not settings.configured:
        where = "найден" if env_path.exists() else "не найден"
        return f"Ключ не настроен ({env_path.name} {where}) — нажмите «Настроить .env»"
    return (
        f"Ключ: {mask(settings.client_id)} · .env: {'найден' if env_path.exists() else 'нет'} · "
        f"Python {sys.version.split()[0]}"
    )


def load_prefs() -> dict:
    try:
        return json.loads(PREFS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_prefs(prefs: dict) -> None:
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        PREFS_FILE.write_text(json.dumps(prefs, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def dashboard_path(action: str = "collect_all", out_dir: Path | None = None) -> Path:
    """Какой файл открывать: демо — только демо, сбор — live с фолбэком на демо."""
    out_dir = out_dir or OUT_DIR
    if action == "demo":
        return out_dir / "dashboard-demo.html"
    live = out_dir / "dashboard.html"
    return live if live.exists() else out_dir / "dashboard-demo.html"


def open_path(path: Path) -> None:
    if os.name == "nt":
        os.startfile(str(path))  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


def run_script(cmd: list[str], on_line, cwd: Path = ROOT) -> int:
    """Запускает run.py и построчно отдаёт вывод в on_line. Возвращает код выхода."""
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(cwd),
        env=env,
        creationflags=CREATE_NO_WINDOW,
    )
    assert process.stdout is not None
    for line in process.stdout:
        on_line(line.rstrip())
    return process.wait()


# --------------------------------------------------------------------------
# Интерфейс
# --------------------------------------------------------------------------
def main() -> int:
    if "--self-test" in sys.argv:
        return self_test()

    try:
        import tkinter as tk
        from tkinter import messagebox, scrolledtext, ttk
    except Exception as exc:  # noqa: BLE001
        print(f"Tkinter недоступен: {exc}")
        return 1

    if os.name == "nt":
        try:
            import ctypes

            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:  # noqa: BLE001
            pass

    class App:
        def __init__(self, root: "tk.Tk") -> None:
            self.root = root
            self.queue: queue.Queue = queue.Queue()
            self.busy = False
            self.buttons: list["tk.Button"] = []
            self.log_lines: list[tuple[str, str | None]] = []

            prefs = load_prefs()
            self.prefs = prefs
            self.theme = prefs.get("theme", "dark")
            self.p = THEMES.get(self.theme, THEMES["dark"])

            self.days_var = tk.StringVar(value=str(prefs.get("days", 30)))
            self.browser_var = tk.BooleanVar(value=bool(prefs.get("open_browser", True)))
            self.today_var = tk.BooleanVar(value=bool(prefs.get("include_today", False)))

            root.title("Ozon Analytics")
            root.geometry("1000x680")
            root.minsize(860, 560)

            self._build_ui()
            self.refresh_status()
            self.append_log("Готово к работе. Выберите действие сверху.", "muted")
            if not Settings.from_env().configured:
                self.append_log(
                    "Ключ не найден. Нажмите «Настроить .env» и впишите OZON_CLIENT_ID и OZON_API_KEY.",
                    "error",
                )
            root.after(120, self.poll)
            root.protocol("WM_DELETE_WINDOW", self.on_close)

        # --- построение окна ---------------------------------------------
        def _build_ui(self) -> None:
            p = self.p
            self.buttons = []
            self.root.configure(bg=p["bg"])

            header = tk.Frame(self.root, bg=p["card"], highlightbackground=p["border"], highlightthickness=1)
            header.pack(fill="x", padx=14, pady=(14, 10))
            left = tk.Frame(header, bg=p["card"])
            left.pack(side="left", fill="x", expand=True)
            tk.Label(left, text="Ozon Analytics", bg=p["card"], fg=p["text"],
                     font=("Segoe UI", 17, "bold"), anchor="w").pack(anchor="w", padx=16, pady=(12, 0))
            tk.Label(left, text="Сбор статистики, дашборд и калькулятор прибыли — в одном окне",
                     bg=p["card"], fg=p["muted"], font=("Segoe UI", 9), anchor="w").pack(anchor="w", padx=16, pady=(2, 12))

            right = tk.Frame(header, bg=p["card"])
            right.pack(side="right", padx=14, pady=14)
            label = "Светлая тема" if self.theme == "dark" else "Тёмная тема"
            self.theme_btn = tk.Button(
                right, text=label, command=self.toggle_theme, bg=p["button"], fg=p["text"],
                activebackground=p["button_hover"], activeforeground=p["text"],
                relief="flat", bd=0, highlightthickness=1, highlightbackground=p["border"],
                font=("Segoe UI", 9), padx=12, pady=6, cursor="hand2",
            )
            self.theme_btn.pack()

            box = tk.LabelFrame(
                self.root, text=" Действия ", bg=p["bg"], fg=p["muted"],
                font=("Segoe UI", 9), bd=1, relief="solid", highlightthickness=0,
            )
            box.pack(fill="x", padx=14, pady=(0, 10))
            box.columnconfigure((0, 1, 2), weight=1)

            def button(parent, text, command, accent=False, col=0, row=0, span=1):
                bg = p["accent"] if accent else p["button"]
                fg = "#ffffff" if accent else p["text"]
                btn = tk.Button(
                    parent, text=text, command=command, bg=bg, fg=fg,
                    activebackground=p["accent_hover"] if accent else p["button_hover"],
                    activeforeground="#ffffff" if accent else p["text"],
                    relief="flat", bd=0, highlightthickness=1, highlightbackground=p["border"],
                    font=("Segoe UI", 9, "bold" if accent else "normal"),
                    padx=12, pady=8, cursor="hand2",
                )
                btn.grid(row=row, column=col, columnspan=span, sticky="ew", padx=6, pady=5)
                self.buttons.append(btn)
                return btn

            button(box, ACTIONS["collect_all"], lambda: self.run_action("collect_all"), accent=True, col=0, span=2)
            button(box, ACTIONS["check"], lambda: self.run_action("check"), col=2)
            button(box, ACTIONS["report"], lambda: self.run_action("report"), col=0, row=1)
            button(box, ACTIONS["calc"], lambda: self.run_action("calc"), col=1, row=1)
            button(box, ACTIONS["demo"], lambda: self.run_action("demo"), col=2, row=1)
            button(box, "Открыть дашборд", self.open_dashboard, col=0, row=2)
            button(box, "Открыть папку out", lambda: self.open_folder(OUT_DIR), col=1, row=2)
            button(box, "Очистить лог", self.clear_log, col=2, row=2)

            settings = tk.Frame(box, bg=p["bg"])
            settings.grid(row=3, column=0, columnspan=3, sticky="ew", padx=6, pady=(4, 8))

            tk.Label(settings, text="Период, дней:", bg=p["bg"], fg=p["text"],
                     font=("Segoe UI", 9)).pack(side="left")
            self.spin = tk.Spinbox(
                settings, from_=1, to=365, width=5, textvariable=self.days_var,
                bg=p["input"], fg=p["text"], insertbackground=p["text"],
                buttonbackground=p["button"], relief="flat", bd=0,
                highlightthickness=1, highlightbackground=p["border"], justify="center",
                font=("Segoe UI", 9),
            )
            self.spin.pack(side="left", padx=(6, 14))

            tk.Checkbutton(
                settings, text="открывать браузер", variable=self.browser_var,
                bg=p["bg"], fg=p["text"], activebackground=p["bg"], activeforeground=p["text"],
                selectcolor=p["input"], font=("Segoe UI", 9), bd=0, highlightthickness=0,
            ).pack(side="left", padx=(0, 12))
            tk.Checkbutton(
                settings, text="включая сегодня", variable=self.today_var,
                bg=p["bg"], fg=p["text"], activebackground=p["bg"], activeforeground=p["text"],
                selectcolor=p["input"], font=("Segoe UI", 9), bd=0, highlightthickness=0,
            ).pack(side="left")

            for text, command in (("Настроить .env", self.edit_env), ("Себестоимость", self.edit_costs)):
                tk.Button(
                    settings, text=text, command=command, bg=p["button"], fg=p["text"],
                    activebackground=p["button_hover"], activeforeground=p["text"],
                    relief="flat", bd=0, highlightthickness=1, highlightbackground=p["border"],
                    font=("Segoe UI", 9), padx=10, pady=5, cursor="hand2",
                ).pack(side="right", padx=(8, 0))

            bottom = tk.Frame(self.root, bg=p["bg"])
            bottom.pack(side="bottom", fill="x", padx=14, pady=(0, 10))
            style = ttk.Style()
            try:
                style.theme_use("clam")
            except Exception:  # noqa: BLE001
                pass
            style.configure(
                "P.Horizontal.TProgressbar",
                troughcolor=p["border"], background=p["accent"],
                bordercolor=p["card"], lightcolor=p["accent"], darkcolor=p["accent"],
            )
            self.progress = ttk.Progressbar(bottom, mode="indeterminate", length=140,
                                            style="P.Horizontal.TProgressbar")
            self.progress.pack(side="left")
            self.status = tk.Label(bottom, text="", bg=p["bg"], fg=p["muted"],
                                   font=("Segoe UI", 9), anchor="w")
            self.status.pack(side="left", fill="x", expand=True, padx=12)

            wrap = tk.Frame(self.root, bg=p["bg"])
            wrap.pack(fill="both", expand=True, padx=14, pady=(0, 8))
            self.log = scrolledtext.ScrolledText(
                wrap, bg=p["log_bg"], fg=p["log_fg"], insertbackground=p["log_fg"],
                selectbackground=p["select"], selectforeground=p["text"],
                relief="flat", bd=0, highlightthickness=1, highlightbackground=p["border"],
                font=("Consolas", 9), wrap="word", state="disabled", padx=10, pady=8, height=8,
            )
            self.log.pack(fill="both", expand=True)
            self.log.tag_configure("error", foreground=p["error"])
            self.log.tag_configure("ok", foreground=p["ok"])
            self.log.tag_configure("cmd", foreground=p["cmd"])
            self.log.tag_configure("muted", foreground=p["muted"])
            try:
                self.log.vbar.configure(
                    bg=p["button"], troughcolor=p["bg"], activebackground=p["border"],
                    bd=0, relief="flat", width=12,
                )
            except Exception:  # noqa: BLE001
                pass

            for text, tag in self.log_lines:
                self._insert_log(text, tag)
            self.set_busy(self.busy)

        # --- тема ---------------------------------------------------------
        def toggle_theme(self) -> None:
            self.theme = "light" if self.theme == "dark" else "dark"
            self.p = THEMES[self.theme]
            self.prefs["theme"] = self.theme
            save_prefs(self.prefs)
            for widget in self.root.winfo_children():
                widget.destroy()
            self._build_ui()
            self.refresh_status()
            self.set_busy(self.busy)

        # --- работа ------------------------------------------------------
        def refresh_status(self) -> None:
            self.status.config(text=status_text(Settings.from_env()))

        def _insert_log(self, text: str, tag: str | None) -> None:
            self.log.configure(state="normal")
            self.log.insert("end", text + "\n", tag or ())
            self.log.see("end")
            self.log.configure(state="disabled")

        def append_log(self, text: str, tag: str | None = None) -> None:
            self.log_lines.append((text, tag))
            if len(self.log_lines) > 3000:
                self.log_lines = self.log_lines[-1500:]
            self._insert_log(text, tag)

        def clear_log(self) -> None:
            self.log_lines = []
            self.log.configure(state="normal")
            self.log.delete("1.0", "end")
            self.log.configure(state="disabled")

        def set_busy(self, busy: bool) -> None:
            self.busy = busy
            state = "disabled" if busy else "normal"
            for btn in self.buttons:
                btn.configure(state=state)
            if busy:
                self.progress.configure(mode="indeterminate")
                self.progress.start(12)
            else:
                self.progress.stop()
                self.progress.configure(mode="determinate", value=0)

        def run_action(self, action: str) -> None:
            if self.busy:
                return
            try:
                days = max(1, int(self.days_var.get()))
            except ValueError:
                days = 30
            self.prefs.update(
                {
                    "days": days,
                    "open_browser": self.browser_var.get(),
                    "include_today": self.today_var.get(),
                    "theme": self.theme,
                }
            )
            save_prefs(self.prefs)

            cmd = build_command(action, days, self.today_var.get())
            self.set_busy(True)
            self.append_log("", None)
            self.append_log(f"» {ACTIONS.get(action, action)}", "cmd")
            threading.Thread(target=self.worker, args=(cmd, action), daemon=True).start()

        def worker(self, cmd: list[str], action: str) -> None:
            try:
                code = run_script(cmd, lambda line: self.queue.put(("log", line)))
            except Exception as exc:  # noqa: BLE001
                self.queue.put(("log", f"Ошибка запуска: {exc}"))
                code = 1
            self.queue.put(("done", code, action))

        def poll(self) -> None:
            try:
                while True:
                    message = self.queue.get_nowait()
                    if message[0] == "log":
                        self.append_log(message[1])
                    else:
                        self.on_finished(message[1], message[2])
            except queue.Empty:
                pass
            self.root.after(120, self.poll)

        def on_finished(self, code: int, action: str) -> None:
            self.set_busy(False)
            self.refresh_status()
            if code == 0:
                self.append_log("Готово.", "ok")
                if action in ("collect_all", "demo") and self.browser_var.get():
                    self.open_dashboard(action)
                elif action == "calc":
                    self.open_calculator()
            elif code == 2:
                self.append_log(
                    "Ошибка: нет ключа или снимка данных — проверьте .env и сначала выполните сбор.",
                    "error",
                )
                messagebox.showwarning(
                    "Не хватает данных",
                    "Нет ключа OZON_CLIENT_ID/OZON_API_KEY или файла data/snapshot.json.\n"
                    "Нажмите «Настроить .env» и сначала соберите данные.",
                )
            else:
                self.append_log("Ошибка — подробности в логе выше", "error")
                messagebox.showerror("Ошибка", "Команда завершилась с ошибкой.\nПодробности — в окне лога.")

        # --- открытие файлов ---------------------------------------------
        def open_dashboard(self, action: str = "collect_all") -> None:
            path = dashboard_path(action)
            if not path.exists():
                messagebox.showinfo("Дашборд", "Отчёта ещё нет. Сначала соберите данные.")
                return
            open_path(path)

        def open_calculator(self) -> None:
            path = OUT_DIR / "calculator.html"
            if not path.exists():
                messagebox.showinfo("Калькулятор", "Сначала нажмите «Калькулятор прибыли».")
                return
            open_path(path)

        def open_folder(self, folder: Path) -> None:
            folder.mkdir(parents=True, exist_ok=True)
            open_path(folder)

        def edit_env(self) -> None:
            if not DEFAULT_ENV.exists():
                example = ROOT / ".env.example"
                if example.exists():
                    DEFAULT_ENV.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
            self._notepad(DEFAULT_ENV, "Впишите OZON_CLIENT_ID и OZON_API_KEY, сохраните и закройте блокнот.")
            self.refresh_status()

        def edit_costs(self) -> None:
            costs = ROOT / "costs.csv"
            if not costs.exists():
                example = ROOT / "costs.example.csv"
                if example.exists():
                    costs.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
            self._notepad(costs, "Формат: sku,offer_id,cost. Достаточно одного из ключей.")

        def _notepad(self, path: Path, hint: str) -> None:
            try:
                self.append_log(hint, "muted")
                if os.name == "nt":
                    subprocess.run(["notepad.exe", str(path)], check=False)
                else:
                    open_path(path)
            except OSError as exc:
                messagebox.showerror("Файл", f"Не удалось открыть {path}: {exc}")

        def on_close(self) -> None:
            if self.busy and not messagebox.askokcancel(
                "Идёт работа", "Команда ещё выполняется. Закрыть окно?"
            ):
                return
            self.root.destroy()

    root = tk.Tk()
    App(root)
    root.mainloop()
    return 0


def self_test() -> int:
    """Проверка без окна: команды собираются правильно, темы на месте."""
    settings = Settings()
    print("python:", python_exe())
    for action in ACTIONS:
        print(f"{action:12s} -> {' '.join(build_command(action, 14, True)[2:])}")
    print("status:", status_text(settings))
    print("темы:", ", ".join(THEMES), "| по умолчанию: dark")
    return 0


if __name__ == "__main__":
    sys.exit(main())
