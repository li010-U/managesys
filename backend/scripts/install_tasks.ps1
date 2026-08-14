# Windows ??????/???????????????????
# ??: powershell -ExecutionPolicy Bypass -File scripts\install_tasks.ps1 [-Remove]
param([switch]$Remove)

$ErrorActionPreference = "Continue"
$BackendDir = Split-Path -Parent $PSScriptRoot
$RepoRoot   = Split-Path -Parent $BackendDir
$VenvPy     = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$SystemPy   = "C:\Users\34003\AppData\Local\Programs\Python\Python314\python.exe"
$Python = if (Test-Path $VenvPy) { $VenvPy } elseif (Test-Path $SystemPy) { $SystemPy } else { "python" }
$bakTask = "managesys_daily_backup"
$bootTask = "managesys_backend_guardian"
$checkTask = "managesys_data_check"

if ($Remove) {
    schtasks /Delete /TN $bakTask /F 2>$null
    schtasks /Delete /TN $bootTask /F 2>$null
    schtasks /Delete /TN $checkTask /F 2>$null
    Write-Host "???????: $bakTask, $bootTask, $checkTask"
    exit 0
}

# 1) ?? 03:00 ????
$bakCmd = "`"$Python`" `"$BackendDir\scripts\auto_backup.py`" --keep 30 --log `"$BackendDir\backups\auto_backup.log`""
schtasks /Create /TN $bakTask /TR $bakCmd /SC DAILY /ST 03:00 /F
Write-Host "???????: $bakTask (?? 03:00)"

# 2) ?? 03:30 ?????????????
$checkCmd = "`"$Python`" `"$BackendDir\scripts\auto_check_data.py`" --fix --log `"$BackendDir\data\auto_check_data.log`""
schtasks /Create /TN $checkTask /TR $checkCmd /SC DAILY /ST 03:30 /F
Write-Host "?????????: $checkTask (?? 03:30)"

# 3) ???????????
$bootCmd = "powershell -ExecutionPolicy Bypass -File `"$BackendDir\scripts\start_backend.ps1`""
schtasks /Create /TN $bootTask /TR $bootCmd /SC ONLOGON /RL HIGHEST /F
Write-Host "?????????: $bootTask"

Write-Host "?????? schtasks /Query /TN $bakTask,$checkTask,$bootTask ??"
