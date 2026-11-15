@echo off
net session >nul 2>&1 || (powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs" & exit /b)
mkdir "C:\Program Files\Common Files\VST3\SpartitoS1.vst3\Contents\x86_64-win" >nul 2>&1
copy /Y "%~dp0SpartitoS1.vst3\Contents\x86_64-win\SpartitoS1.vst3" "C:\Program Files\Common Files\VST3\SpartitoS1.vst3\Contents\x86_64-win\SpartitoS1.vst3"
if errorlevel 1 (echo BLAD: zamknij Studio One i sprobuj jeszcze raz.) else (echo Gotowe: Spartito S1 0.1.0 zainstalowane.)
timeout /t 8 >nul
