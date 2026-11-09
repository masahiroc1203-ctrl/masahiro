@echo off
rem ==========================================================
rem  nas-backup launcher for Windows (Buffalo LinkStation LS720D)
rem  1. Put this file in the same folder as nas-backup-windows-amd64.exe
rem  2. Change BACKUP_DIR below to your LS720D shared folder
rem  3. Double-click this file
rem ==========================================================

rem LS720D shared folder (\\IP-address\share-name\folder)
set BACKUP_DIR=\\192.168.1.50\share\SmartphoneBackup

rem Optional: password asked on the phone (leave empty for none)
set BACKUP_PASSWORD=

rem date = sort into YYYY\YYYY-MM folders / flat = no sub folders
set BACKUP_LAYOUT=date

cd /d "%~dp0"
nas-backup-windows-amd64.exe
pause
