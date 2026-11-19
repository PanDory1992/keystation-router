@echo off
chcp 65001 >nul
title Skaner Mega - podglad
set "PYTHONIOENCODING=utf-8"
set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not exist "%PY%" set "PY=py"
"%PY%" "%~dp0mega.py" skaner
echo.
pause
