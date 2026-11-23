@echo off
rem MiniDesktop-Setup.exe uretir (PyInstaller + Inno Setup).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\build.ps1"
pause
