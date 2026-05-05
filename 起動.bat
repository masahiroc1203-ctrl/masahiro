@echo off
cd /d "%~dp0"
echo デスクトップ負荷モニターを起動しています...
start "" http://localhost:8080
python monitor.py
pause
