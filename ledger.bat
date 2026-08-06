@echo off
rem Windows wrapper for tools/claude_ledger.py
rem   - uses "python" (not python3)
rem   - runs in UTF-8 mode so redirected output is not mojibake / UnicodeEncodeError
rem   - always runs from the repository root
rem Usage:  ledger scan | ledger all | ledger daily --days 7
cd /d "%~dp0"
python -X utf8 tools\claude_ledger.py %*
