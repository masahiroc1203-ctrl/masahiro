@echo off
rem ============================================================
rem  月次収支レポートをワンクリックで作成するバッチファイル
rem  (このファイルは Shift_JIS で保存すること)
rem
rem  使い方: このファイルをダブルクリックするだけ。
rem  成功するとレポートが自動でブラウザに表示されます。
rem
rem  前提: Docker の PostgreSQL (expense_db) が起動していること
rem        (起動していなければ docker-compose up -d を実行)
rem ============================================================
cd /d "%~dp0"

rem Python コマンドを探す(python が無ければ py を使う)
set PY=python
where python >nul 2>nul || set PY=py

%PY% report.py ^
  --dsn "postgresql://appuser:secret@localhost:5432/expense" ^
  --query-file "queries\postgres-local-db.sql" ^
  --out report.html

if errorlevel 1 (
  echo.
  echo ============================================================
  echo  レポートの作成に失敗しました。上のエラーを確認してください。
  echo.
  echo  よくある原因:
  echo   - DB が起動していない場合は docker-compose up -d を実行
  echo   - psycopg が無い場合は pip install psycopg2-binary を実行
  echo ============================================================
  pause
  exit /b 1
)

start "" report.html
