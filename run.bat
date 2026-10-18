@echo off
chcp 65001 >nul
setlocal

rem Переходим в папку скрипта. pushd, а не cd: работает и для сетевых путей.
pushd "%~dp0" 2>nul
if errorlevel 1 (
    echo.
    echo Не удалось открыть папку проекта: %~dp0
    echo Запустите run.bat из локальной папки на диске.
    echo.
    pause
    exit /b 1
)

rem --- ищем py (основной), затем python; заглушка Microsoft Store версию не печатает ---
set "PY="
for /f "delims=" %%v in ('py --version 2^>nul ^| findstr /r "[0-9][.][0-9]"') do set "PY=py"
if not defined PY (
    for /f "delims=" %%v in ('python --version 2^>nul ^| findstr /r "[0-9][.][0-9]"') do set "PY=python"
)

if not defined PY (
    echo.
    echo Python не найден ни как "py", ни как "python".
    echo Python not found as "py" or "python".
    echo Если установлена заглушка Microsoft Store, она не запускает скрипты.
    echo The Microsoft Store stub cannot run scripts.
    echo.
    echo Установите Python 3.10+ / Install Python 3.10+: https://www.python.org/downloads/
    echo Отметьте "Add python.exe to PATH" / Check "Add python.exe to PATH".
    echo.
    pause
    popd
    exit /b 1
)

set "PYTHONIOENCODING=utf-8"
set "DASH=%~dp0out\dashboard-demo.html"

if "%~1"=="" (
    echo Запускаю демо-дашборд ^(ключ не нужен^)...
    echo.
    %PY% run.py demo
    if exist "%DASH%" (
        echo.
        echo Открываю дашборд в браузере...
        start "" "%DASH%"
    ) else (
        echo.
        echo Дашборд не создан — смотрите сообщение об ошибке выше.
    )
) else (
    %PY% run.py %*
)

if errorlevel 1 pause
popd
endlocal
