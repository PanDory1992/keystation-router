@echo off
chcp 65001 >nul
title Router - restart
type nul > "%~dp0restart-router"
echo Poproszono router o restart. Za ok. 5 sekund wstanie sam (nadzorca go podniesie).
echo Sprawdz potem wtyczke Keystation Status albo zagraj nute.
timeout /t 8
