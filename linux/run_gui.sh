#!/usr/bin/env bash
# Запуск графического интерфейса Ozon Analytics на Ubuntu/Linux.
#
# Требуется Python 3.10+, Tkinter и графическая сессия.
# Установка Tkinter:
#   sudo apt update && sudo apt install -y python3-tk xdg-utils
#
# Запуск:
#   ./linux/run_gui.sh
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

die() {
    printf 'Ошибка: %s\n' "$*" >&2
    exit 1
}

find_python() {
    if [[ -n "${PYTHON:-}" ]]; then
        printf '%s\n' "$PYTHON"
        return 0
    fi
    local candidate
    for candidate in python3 python3.13 python3.12 python3.11 python3.10; do
        if command -v "$candidate" >/dev/null 2>&1; then
            if "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1; then
                printf '%s\n' "$candidate"
                return 0
            fi
        fi
    done
    return 1
}

PYTHON_BIN="$(find_python || true)"
if [[ -z "$PYTHON_BIN" ]]; then
    cat >&2 <<'EOF'
Python 3.10+ не найден.

Ubuntu/Debian:
  sudo apt update
  sudo apt install -y python3 python3-tk xdg-utils

Проверка:
  python3 --version
EOF
    exit 1
fi

command -v "$PYTHON_BIN" >/dev/null 2>&1 || die "интерпретатор не найден: $PYTHON_BIN"
[[ -f gui.py ]] || die "в корне проекта нет gui.py"

if ! "$PYTHON_BIN" -c 'import tkinter' >/dev/null 2>&1; then
    cat >&2 <<'EOF'
Tkinter не установлен — без него графическое окно не запустится.

Ubuntu/Debian:
  sudo apt update
  sudo apt install -y python3-tk

Проверка:
  python3 -c 'import tkinter; print(tkinter.TkVersion)'
EOF
    exit 1
fi

if [[ -z "${DISPLAY:-}" ]]; then
    cat >&2 <<'EOF'
Нет X11-дисплея: переменная DISPLAY пуста.

Tkinter на Ubuntu работает через X11/XWayland. Запустите скрипт из терминала
Ubuntu Desktop (не по SSH без X11-форвардинга). В headless-среде используйте
командный интерфейс:
  ./linux/run.sh check
  ./linux/run.sh all --days 30
EOF
    exit 1
fi

export PYTHONIOENCODING=utf-8
export PYTHONUTF8=1

exec "$PYTHON_BIN" gui.py "$@"
