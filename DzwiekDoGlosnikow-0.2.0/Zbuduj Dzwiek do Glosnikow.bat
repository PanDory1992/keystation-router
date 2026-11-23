@echo off
setlocal
rem Gotowa wtyczka jest juz w folderze. To tylko na wypadek zmian w zrodlach (Rust MSVC + Build Tools sa na PC).
call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat" >nul
cd /d "%~dp0zrodla"
"%USERPROFILE%\.cargo\bin\cargo.exe" test --release
if errorlevel 1 (echo Testy nie przeszly. Wtyczka NIE zostala podmieniona. & pause & exit /b 1)
"%USERPROFILE%\.cargo\bin\cargo.exe" build --release
if errorlevel 1 (echo Budowanie nie powiodlo sie. & pause & exit /b 1)
copy /Y "target\release\dzwiek_do_glosnikow.dll" "%~dp0DzwiekDoGlosnikow.vst3\Contents\x86_64-win\DzwiekDoGlosnikow.vst3" >nul
echo Gotowe. Teraz "Zainstaluj Dzwiek do Glosnikow.bat".
pause
