@echo off
chcp 65001 >nul
title Skaner Mega - test jednej linii
set "PYTHONIOENCODING=utf-8"
set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not exist "%PY%" set "PY=py"
rem 20.11: rozpoznanie tylko dla klawiszy linii Y2 (D4, Bb4, Gb5) i ich sasiadow; na koncu skaner wraca sam
"%PY%" "%~dp0mega.py" rozpoznaj --klawisze 61,62,63,69,70,71,77,78,79
echo.
pause
