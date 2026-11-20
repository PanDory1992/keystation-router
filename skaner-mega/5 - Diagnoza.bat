@echo off
chcp 65001 >nul
title Skaner Mega - diagnoza
set "PYTHONIOENCODING=utf-8"
set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not exist "%PY%" set "PY=py"
rem 20.11 (MEGA 2.0): bez wgrywania. Wersja skanera, test linii, bledy lacza; wynik w wyniki\diagnoza-*.txt
"%PY%" "%~dp0mega.py" diagnoza
echo.
pause
