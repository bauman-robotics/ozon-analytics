@echo off
chcp 65001 >nul
setlocal

pushd "%~dp0" 2>nul
if errorlevel 1 (
    echo.
    echo Не удалось открыть папку проекта: %~dp0
    echo Запустите run_gui.bat из локальной папки на диске.
    echo.
    pause
    exit /b 1
)

rem pyw запускает окно без чёрной консоли; если его нет — обычный py
where pyw >nul 2>nul
if not errorlevel 1 (
    start "" pyw "%~dp0gui.py"
) else (
    start "" py "%~dp0gui.py"
)

popd
endlocal
