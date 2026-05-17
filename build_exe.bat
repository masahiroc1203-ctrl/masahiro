@echo off
setlocal

echo ============================================
echo   Build Script - Video Editing Tool
echo ============================================
echo.

:: Python check
python --version > nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found.
    echo Please install Python from https://www.python.org/
    pause & exit /b 1
)

:: Step 1: Install libraries
echo Step 1/4: Installing libraries...
pip install -r requirements.txt -q
if errorlevel 1 (
    echo ERROR: pip install failed.
    pause & exit /b 1
)
pip install pyinstaller -q
if errorlevel 1 (
    echo ERROR: pyinstaller install failed.
    pause & exit /b 1
)
echo Done.

:: Step 2: FFmpeg check / download
echo Step 2/4: Checking FFmpeg...
if exist "ffmpeg\ffmpeg.exe" (
    echo ffmpeg\ffmpeg.exe found.
) else (
    echo FFmpeg not found. Downloading...
    if not exist "ffmpeg" mkdir ffmpeg
    powershell -NoProfile -ExecutionPolicy Bypass -Command "$url='https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip'; $zip='ffmpeg_tmp.zip'; Write-Host 'Downloading...'; Invoke-WebRequest -Uri $url -OutFile $zip -UseBasicParsing; Write-Host 'Extracting...'; Expand-Archive -Path $zip -DestinationPath 'ffmpeg_extract' -Force; $exe=Get-ChildItem 'ffmpeg_extract' -Recurse -Filter 'ffmpeg.exe' | Select-Object -First 1; Copy-Item $exe.FullName 'ffmpeg\ffmpeg.exe'; Remove-Item $zip -Force; Remove-Item 'ffmpeg_extract' -Recurse -Force; Write-Host 'FFmpeg ready.'"
    if errorlevel 1 (
        echo ERROR: FFmpeg download failed.
        echo Please download manually from:
        echo https://github.com/BtbN/FFmpeg-Builds/releases
        echo and place ffmpeg.exe into the ffmpeg\ folder.
        pause & exit /b 1
    )
)

:: Step 3: Build exe
echo Step 3/4: Building exe (this takes several minutes)...
if exist "dist\VideoEditTool" rmdir /s /q "dist\VideoEditTool"
python -m PyInstaller video_editor.spec --noconfirm
if errorlevel 1 (
    echo ERROR: Build failed.
    pause & exit /b 1
)
echo Done.

:: Step 4: Copy FFmpeg into dist
echo Step 4/4: Finalizing...
if not exist "dist\VideoEditTool\ffmpeg" mkdir "dist\VideoEditTool\ffmpeg"
if exist "ffmpeg\ffmpeg.exe" (
    copy "ffmpeg\ffmpeg.exe" "dist\VideoEditTool\ffmpeg\" > nul
)
echo Done.

echo.
echo ============================================
echo   Build Complete!
echo ============================================
echo.
echo   Folder : dist\VideoEditTool\
echo   Launch : dist\VideoEditTool\VideoEditTool.exe
echo.
echo   Zip the folder and share it.
echo ============================================
pause
