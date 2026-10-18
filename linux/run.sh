#!/usr/bin/env bash
# Запуск Ozon Analytics на Ubuntu/Linux.
#
# Примеры:
#   ./linux/run.sh                  # live-отчёт за 30 дней (нужен .env)
#   ./linux/run.sh check            # проверить ключ, роли и срок действия
#   ./linux/run.sh all --days 30    # собрать данные и дашборд
#   ./linux/run.sh report           # пересобрать отчёт из готового снимка
#   ./linux/run.sh demo             # демо без ключа (или ./linux/run_demo.sh)
#   ./linux/run.sh serve            # локальный сервер для out/
#
# Python 3.10+ ищется автоматически: python3, python3.13, python3.12, ...
# Можно указать интерпретатор явно: PYTHON=python3.12 ./linux/run.sh check
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
  sudo apt install -y python3 python3-venv

Проверка:
  python3 --version   # должно быть 3.10 или новее

Если Python установлен под другим именем, укажите его явно:
  PYTHON=python3.12 ./linux/run.sh check
EOF
    exit 1
fi

command -v "$PYTHON_BIN" >/dev/null 2>&1 || die "интерпретатор не найден: $PYTHON_BIN"
[[ -f run.py ]] || die "в корне проекта нет run.py"

export PYTHONIOENCODING=utf-8
export PYTHONUTF8=1

if [[ $# -eq 0 ]]; then
    if [[ ! -f .env ]]; then
        cat <<'EOF'
Файл .env не найден — live-данные без ключа не загрузить.

  1. cp .env.example .env
  2. nano .env      # впишите OZON_CLIENT_ID и OZON_API_KEY
  3. ./linux/run.sh check
  4. ./linux/run.sh all --days 30

Посмотреть демо без ключа:
  ./linux/run_demo.sh
EOF
        exit 2
    fi
    set -- all --days 30
fi

exec "$PYTHON_BIN" run.py "$@"
