@echo off
rem One-click monthly budget report (see README.md)
rem Requires: Docker PostgreSQL (expense_db) running.
cd /d "%~dp0"

set PY=python
where python >nul 2>nul || set PY=py

%PY% report.py --dsn "postgresql://appuser:secret@localhost:5432/expense" --query-file "queries\postgres-local-db.sql" --out report.html

if errorlevel 1 (
  echo.
  echo *** FAILED - see the message above ***
  pause
  exit /b 1
)

start "" report.html
