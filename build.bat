@echo off
rem Builds dist\MiniDesktop-Setup-<VERSION>.exe (PyInstaller + Inno Setup).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\build.ps1"
pause
