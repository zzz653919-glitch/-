@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul

set PY=
for %%V in (3.13 3.12 3.11 3.10) do (
    if not defined PY (
        py -%%V -c "import sys" >nul 2>nul && set PY=py -%%V
    )
)
if not defined PY (
    echo Python 3.10-3.13 topilmadi. 3.14 hali to'liq sinalmagan. https://www.python.org/downloads/ dan Python 3.13 ni o'rnating.
    pause
    exit /b 1
)
echo Ishlatiladigan Python: %PY%

if not exist ".venv\Scripts\python.exe" (
    echo [1/3] Virtual muhit yaratilmoqda...
    %PY% -m venv .venv || goto :error
)
if not exist ".venv\.installed" (
    echo [2/3] Kutubxonalar o'rnatilmoqda ^(birinchi ishga tushirishda bir necha daqiqa^)...
    ".venv\Scripts\python.exe" -m pip install --upgrade pip >nul
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt || goto :error
    echo ok> ".venv\.installed"
)
echo [3/3] ПЯТНИЦА ishga tushmoqda...
start "" ".venv\Scripts\pythonw.exe" main.py
exit /b 0

:error
echo.
echo Xatolik yuz berdi. Python 3.10-3.13 o'rnatilganini va internet borligini tekshiring.
pause
exit /b 1
