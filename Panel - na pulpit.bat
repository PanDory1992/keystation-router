@echo off
rem Panel Keystation: skrot na pulpicie + jednorazowy restart nadzorcy (nowa wersja z restartami na zlecenie).
set "HERE=%~dp0"
set "PYW=%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$d=[Environment]::GetFolderPath('Desktop'); $s=(New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $d 'Panel Keystation.lnk')); $s.TargetPath=$env:PYW; $s.Arguments='\"' + $env:HERE + 'panel_sterowania.py\"'; $s.WorkingDirectory=$env:HERE; $s.IconLocation=$env:HERE + 'trener\Trener.ico,0'; $s.Description='Router, most, Trener, nadzorca'; $s.Save(); 'Skrot Panel Keystation jest na pulpicie.'"
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name like 'python%%'\" | Where-Object { $_.CommandLine -like '*keystation_supervisor.py*' } | ForEach-Object { Invoke-CimMethod -InputObject $_ -MethodName Terminate | Out-Null }"
start "" "%PYW%" "%HERE%keystation_supervisor.py"
start "" "%PYW%" "%HERE%panel_sterowania.py"
echo Gotowe. Nadzorca uruchomiony od nowa, panel otwarty.
timeout /t 5 >nul
