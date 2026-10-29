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
if not exist ".venv\Scripts\python.exe" (%PY% -m venv .venv || goto :error)
".venv\Scripts\python.exe" -m pip install -r requirements.txt pyinstaller || goto :error
".venv\Scripts\pyinstaller.exe" --noconfirm --clean --windowed --name Pyatnitsa ^
  --collect-all speech_recognition --collect-all edge_tts --collect-all sounddevice ^
  --hidden-import pythoncom --hidden-import pyttsx3.drivers.sapi5 main.py || goto :error
echo.
echo Tayyor: dist\Pyatnitsa\Pyatnitsa.exe  ^(butun dist\Pyatnitsa papkasini ko'chirish mumkin^)
pause
exit /b 0
:error
echo Yig'ishda xatolik yuz berdi.
pause
exit /b 1
