@echo off
net session >nul 2>&1 || (powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs" & exit /b)
xcopy /E /I /Y "%~dp0DzwiekZPC.vst3" "C:\Program Files\Common Files\VST3\DzwiekZPC.vst3" >nul
if errorlevel 1 (echo BLAD: zamknij Studio One i sprobuj jeszcze raz.) else (echo Gotowe: Dzwiek z PC 0.1.0 zainstalowany.)
timeout /t 8 >nul
