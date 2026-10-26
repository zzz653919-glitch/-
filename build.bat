@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul
where py >nul 2>nul
if %errorlevel%==0 (set PY=py -3) else (set PY=python)
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
