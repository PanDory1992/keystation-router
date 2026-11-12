@echo off
net session >nul 2>&1 || (powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs" & exit /b)
copy /Y "%~dp0Uszy-nowy.vst3" "C:\Program Files\Common Files\VST3\Uszy.vst3"
copy /Y "%~dp0Uszy2.vst3" "C:\Program Files\Common Files\VST3\Uszy2.vst3"
if errorlevel 1 (echo BLAD: zamknij Studio One i sprobuj jeszcze raz.) else (echo Gotowe: Uszy zaktualizowane.)
timeout /t 8 >nul
