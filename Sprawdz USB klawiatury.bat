@echo off
echo Sprawdzam, co klawiatura pokazuje przez USB (tylko odczyt)...
powershell -NoProfile -ExecutionPolicy Bypass -Command "& { $o = '%~dp0usb-klawiatura.txt'; Get-PnpDevice | Where-Object { $_.InstanceId -match 'VID_0A4D' } | ForEach-Object { '=== ' + $_.FriendlyName + ' | klasa: ' + $_.Class + ' | stan: ' + $_.Status + ' | obecne: ' + $_.Present; $_.InstanceId; Get-PnpDeviceProperty -InstanceId $_.InstanceId -KeyName 'DEVPKEY_Device_HardwareIds','DEVPKEY_Device_CompatibleIds','DEVPKEY_Device_Service','DEVPKEY_Device_DriverInfPath','DEVPKEY_Device_BusReportedDeviceDesc' -ErrorAction SilentlyContinue | ForEach-Object { '  ' + $_.KeyName + ' = ' + ($_.Data -join '; ') }; '' } | Out-File -Encoding utf8 $o; Write-Host 'Gotowe, zapisano:' $o }"
pause
