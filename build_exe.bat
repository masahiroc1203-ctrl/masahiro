@echo off
chcp 65001 > nul
echo ============================================
echo   動画自動編集ツール　ビルドスクリプト
echo ============================================
echo.

:: Python 確認
python --version > nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python が見つかりません。
    echo https://www.python.org/ からインストールしてください。
    pause & exit /b 1
)

:: 依存ライブラリのインストール
echo [1/4] ライブラリをインストール中...
pip install -r requirements.txt -q
pip install pyinstaller -q
echo       完了

:: FFmpeg の確認・ダウンロード
echo [2/4] FFmpeg を確認中...
if exist "ffmpeg\ffmpeg.exe" (
    echo       ffmpeg\ffmpeg.exe が見つかりました
) else (
    echo       FFmpeg が見つかりません。ダウンロード中...
    if not exist "ffmpeg" mkdir ffmpeg
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
        "$url='https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip';" ^
        "$zip='ffmpeg_tmp.zip';" ^
        "Write-Host '  ダウンロード中 (数十秒かかります)...';" ^
        "Invoke-WebRequest -Uri $url -OutFile $zip -UseBasicParsing;" ^
        "Write-Host '  展開中...';" ^
        "Expand-Archive -Path $zip -DestinationPath 'ffmpeg_extract' -Force;" ^
        "$exe=Get-ChildItem 'ffmpeg_extract' -Recurse -Filter 'ffmpeg.exe' | Select-Object -First 1;" ^
        "Copy-Item $exe.FullName 'ffmpeg\ffmpeg.exe';" ^
        "Remove-Item $zip -Force;" ^
        "Remove-Item 'ffmpeg_extract' -Recurse -Force;" ^
        "Write-Host '  FFmpeg の準備完了'"
    if errorlevel 1 (
        echo [ERROR] FFmpeg のダウンロードに失敗しました。
        echo 手動で以下からダウンロードし、ffmpeg\ フォルダに ffmpeg.exe を配置してください。
        echo https://github.com/BtbN/FFmpeg-Builds/releases
        pause & exit /b 1
    )
)

:: ビルド
echo [3/4] exe をビルド中 (数分かかります)...
if exist "dist\動画編集ツール" rmdir /s /q "dist\動画編集ツール"
pyinstaller video_editor.spec --noconfirm
if errorlevel 1 (
    echo [ERROR] ビルドに失敗しました。
    pause & exit /b 1
)
echo       完了

:: 後処理
echo [4/4] 後処理...
:: FFmpeg を dist フォルダにもコピー（同梱確認）
if not exist "dist\動画編集ツール\ffmpeg" (
    mkdir "dist\動画編集ツール\ffmpeg"
    copy "ffmpeg\ffmpeg.exe" "dist\動画編集ツール\ffmpeg\" > nul
)
echo       完了

echo.
echo ============================================
echo   ビルド完了！
echo ============================================
echo.
echo   配布フォルダ: dist\動画編集ツール\
echo   起動ファイル: dist\動画編集ツール\動画編集ツール.exe
echo.
echo   フォルダごと zip 圧縮して配布してください。
echo ============================================
pause
