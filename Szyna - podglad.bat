@echo off
chcp 65001 >nul
title Szyna routera - podglad
set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not exist "%PY%" set "PY=py"
"%PY%" "%~dp0szyna_podglad.py"
pause
