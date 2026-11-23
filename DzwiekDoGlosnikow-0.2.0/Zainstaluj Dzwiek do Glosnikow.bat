@echo off
if not exist "%~dp0DzwiekDoGlosnikow.vst3\Contents\x86_64-win\DzwiekDoGlosnikow.vst3" (
  echo BLAD: brak wtyczki w folderze. Uruchom najpierw "Zbuduj Dzwiek do Glosnikow.bat".
  pause
  exit /b 1
)
net session >nul 2>&1 || (powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs" & exit /b)
xcopy /E /I /Y "%~dp0DzwiekDoGlosnikow.vst3" "C:\Program Files\Common Files\VST3\DzwiekDoGlosnikow.vst3" >nul
if errorlevel 1 (echo BLAD: zamknij Studio One i sprobuj jeszcze raz.) else (echo Gotowe: Dzwiek do Glosnikow 0.2.2 zainstalowany. Uruchom Studio One.)
timeout /t 8 >nul
