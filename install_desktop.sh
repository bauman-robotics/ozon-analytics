#!/usr/bin/env bash
# Добавляет ярлык «Ozon Analytics» в меню приложений Ubuntu/GNOME.
#
# Запуск:
#   ./install_desktop.sh
#
# После этого приложение можно найти в меню приложений по имени Ozon Analytics.
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
DESKTOP_FILE="$APP_DIR/ozon-analytics.desktop"

[[ -f "$SCRIPT_DIR/run_gui.sh" ]] || {
    echo "Ошибка: рядом нет run_gui.sh" >&2
    exit 1
}

mkdir -p "$APP_DIR"

cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=Ozon Analytics
GenericName=Ozon Analytics
Comment=Аналитика Ozon Seller API: дашборд и калькулятор прибыли
Exec="$SCRIPT_DIR/run_gui.sh"
Path=$SCRIPT_DIR
Icon=$SCRIPT_DIR/docs/ozon-analytics.svg
Terminal=false
Categories=Office;Finance;
Keywords=ozon;analytics;dashboard;калькулятор;
StartupNotify=true
EOF

chmod +x "$DESKTOP_FILE"

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$APP_DIR" >/dev/null 2>&1 || true
fi

echo "Ярлык установлен: $DESKTOP_FILE"
echo "Откройте меню приложений Ubuntu и найдите «Ozon Analytics»."
echo
echo "Если ярлык не появился, выйдите и войдите в сессию заново"
echo "или запустите приложение напрямую: $SCRIPT_DIR/run_gui.sh"
