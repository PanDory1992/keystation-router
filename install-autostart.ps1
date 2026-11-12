# Keystation MIDI services - autostart via Task Scheduler (Claude, 01.11.2026)
# Run once:  powershell -ExecutionPolicy Bypass -File "$env:LOCALAPPDATA\CodexPedalModes\install-autostart.ps1"
$ErrorActionPreference = 'Stop'
$root    = "$env:LOCALAPPDATA\CodexPedalModes"
$pyw     = "$env:LOCALAPPDATA\Programs\Python\Python312\pythonw.exe"
$startup = [Environment]::GetFolderPath('Startup')
$backup  = Join-Path $root 'startup-backup'

# 1. stop old copies (router, bridge, supervisor)
Get-CimInstance Win32_Process -Filter "Name like 'python%'" |
  Where-Object { $_.CommandLine -match 'pedal_router|studio_one_bridge|keystation_supervisor' } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
Start-Sleep 2

# 2. old Startup shortcuts -> backup (the scheduled task replaces them)
New-Item -ItemType Directory -Force $backup | Out-Null
foreach ($n in 'Keystation Pedal Modes.lnk', 'Codex Studio One MIDI Bridge.lnk') {
  $p = Join-Path $startup $n
  if (Test-Path $p) { Move-Item $p (Join-Path $backup $n) -Force }
}

# 3. scheduled task: at logon, 5 s delay, restart on failure, never time-limited
$action   = New-ScheduledTaskAction -Execute $pyw -Argument "`"$root\keystation_supervisor.py`"" -WorkingDirectory $root
$trigger  = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$trigger.Delay = 'PT5S'
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
            -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) `
            -MultipleInstances IgnoreNew -StartWhenAvailable
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName 'Keystation MIDI Services' -Action $action -Trigger $trigger `
  -Settings $settings -Principal $principal -Force | Out-Null

# 4. start now and show state
Start-ScheduledTask -TaskName 'Keystation MIDI Services'
Start-Sleep 8
Get-Content "$root\supervisor.log" -Tail 6
Write-Host "`nOK - teraz mozesz otworzyc Studio One." -ForegroundColor Green
