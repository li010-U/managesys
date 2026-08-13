# ?? Windows ????????? + ???????????
# ??:   powershell -ExecutionPolicy Bypass -File scripts\install_tasks.ps1 [-Remove]
param([switch]$Remove)

$ErrorActionPreference = "Continue"
$BackendDir = Split-Path -Parent $PSScriptRoot
$Python = "C:\Users\34003\AppData\Local\Programs\Python\Python314\python.exe"
if (-not (Test-Path $Python)) { $Python = "python" }

$bakTask = "managesys_daily_backup"
$bootTask = "managesys_backend_guardian"

if ($Remove) {
    schtasks /Delete /TN $bakTask /F 2>$null
    schtasks /Delete /TN $bootTask /F 2>$null
    Write-Host "???????: $bakTask, $bootTask"
    exit 0
}

# 1) ?? 03:00 ????
$bakCmd = "`"$Python`" `"$BackendDir\scripts\auto_backup.py`" --keep 30 --log `"$BackendDir\backups\auto_backup.log`""
schtasks /Create /TN $bakTask /TR $bakCmd /SC DAILY /ST 03:00 /F
Write-Host "???????: $bakTask (?? 03:00)"

# 2) ?????????????? guardian????????
$bootCmd = "powershell -ExecutionPolicy Bypass -File `"$BackendDir\scripts\start_backend.ps1`""
schtasks /Create /TN $bootTask /TR $bootCmd /SC ONLOGON /RL HIGHEST /F
Write-Host "?????????: $bootTask"

Write-Host "????? schtasks /Query /TN $bakTask ? $bootTask ???"
