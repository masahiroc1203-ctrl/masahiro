@echo off
rem ============================================================
rem  Windows 用ラッパー: tools\claude_ledger.py
rem    - python / py -3 のどちらでも動くように自動判別
rem    - UTF-8 モードで実行（リダイレクト時の文字化け・例外を防ぐ）
rem    - 常にリポジトリルートを作業ディレクトリにする
rem  使い方:  ledger scan | ledger all | ledger daily --days 7
rem ============================================================
setlocal
cd /d "%~dp0"

set "PY="
where python >nul 2>nul && set "PY=python"
if not defined PY (
    where py >nul 2>nul && set "PY=py -3"
)
if not defined PY (
    echo [ledger] Python が見つかりません。
    echo          https://www.python.org/downloads/ からインストールし、
    echo          "Add python.exe to PATH" にチェックを入れてください。
    exit /b 1
)

%PY% -X utf8 tools\claude_ledger.py %*
exit /b %errorlevel%
