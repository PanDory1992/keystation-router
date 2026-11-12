@echo off
rem Restartuje nadzorce (router, most Studio One, serwer Trenera). Router i most dzialaja dalej.
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name like 'python%%'\" | Where-Object { $_.CommandLine -like '*keystation_supervisor.py*' } | ForEach-Object { Invoke-CimMethod -InputObject $_ -MethodName Terminate | Out-Null }"
start "" "%LOCALAPPDATA%\Programs\Python\Python312\pythonw.exe" "%~dp0keystation_supervisor.py"
echo Gotowe. Za kilka sekund Trener bedzie dzialal na stale.
timeout /t 5 >nul
