#!/usr/bin/env bash
# Демо-режим Ozon Analytics на Ubuntu/Linux.
#
# Собирает out/dashboard-demo.html на синтетических данных и, если есть
# графическая сессия, открывает его в браузере. Ключ API не нужен.
#
# Примеры:
#   ./run_demo.sh
#   ./run_demo.sh --days 7
#   ./run_demo.sh --no-open      # не открывать браузер
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

open_browser=1
demo_args=()
for arg in "$@"; do
    case "$arg" in
        --no-open) open_browser=0 ;;
        *) demo_args+=("$arg") ;;
    esac
done

if "$SCRIPT_DIR/run.sh" demo "${demo_args[@]}"; then
    status=0
else
    status=$?
fi

if [[ $status -eq 0 ]]; then
    dashboard="$SCRIPT_DIR/out/dashboard-demo.html"
    echo
    if [[ -f "$dashboard" ]]; then
        echo "Демо-дашборд: $dashboard"
        if [[ $open_browser -eq 1 && -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]] \
            && command -v xdg-open >/dev/null 2>&1; then
            xdg-open "$dashboard" >/dev/null 2>&1 &
        elif [[ $open_browser -eq 1 ]]; then
            echo "Графическая сессия не найдена — откройте файл вручную (путь выше)."
        fi
    else
        echo "Дашборд не создан — смотрите сообщение об ошибке выше." >&2
    fi
fi

exit "$status"
