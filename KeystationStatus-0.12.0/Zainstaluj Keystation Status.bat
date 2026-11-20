@echo off
net session >nul 2>&1 || (powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs" & exit /b)
copy /Y "%~dp0KeystationStatus.vst3\Contents\x86_64-win\KeystationStatus.vst3" "C:\Program Files\Common Files\VST3\KeystationStatus.vst3\Contents\x86_64-win\KeystationStatus.vst3"
if errorlevel 1 (echo BLAD: zamknij Studio One i sprobuj jeszcze raz.) else (echo Gotowe: Keystation Status 0.12.0 zainstalowany.)
timeout /t 8 >nul
