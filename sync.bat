@echo off
rem ============================================================
rem  ローカルの使用状況を集計してリポジトリへ反映する（1ステップ）
rem    git pull -> ledger all -> commit -> push
rem  変更が無ければ何もせず終了する。
rem ============================================================
setlocal
cd /d "%~dp0"

for /f "tokens=*" %%b in ('git rev-parse --abbrev-ref HEAD 2^>nul') do set "BRANCH=%%b"
if not defined BRANCH (
    echo [sync] git リポジトリではありません。
    exit /b 1
)
echo [sync] ブランチ: %BRANCH%

echo [1/4] 最新を取得...
git pull --rebase
if errorlevel 1 goto :error

echo [2/4] ログを集計してダッシュボードを生成...
call "%~dp0ledger.bat" all
if errorlevel 1 goto :error

echo [3/4] 変更を確認...
git diff --quiet -- data/sessions.json docs/dashboard.html
if not errorlevel 1 (
    echo        変更はありません。終了します。
    exit /b 0
)

echo [4/4] コミットして push...
git add data/sessions.json docs/dashboard.html
if errorlevel 1 goto :error
git commit -m "Update usage from %COMPUTERNAME%"
if errorlevel 1 goto :error
git push
if errorlevel 1 goto :error

echo [sync] 完了しました。
exit /b 0

:error
set "RC=%errorlevel%"
echo [sync] 失敗しました (エラーコード %RC%)
exit /b %RC%
