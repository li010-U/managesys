# ?????????/?? uvicorn????????
# ??:
#   powershell -ExecutionPolicy Bypass -File scripts\start_backend.ps1           # ?????Ctrl+C ?????
#   powershell -ExecutionPolicy Bypass -File scripts\start_backend.ps1 -Stop     # ????
# ??: -Reload (uvicorn --reload ??????)  -Port 8000  -Host 127.0.0.1
param(
    [switch]$Stop,
    [switch]$Reload,
    [int]$Port = 8000,
    [string]$HostAddr = "127.0.0.1"
)

$ErrorActionPreference = "Stop"
$BackendDir = Split-Path -Parent $PSScriptRoot
$FixedPython = "C:\Users\34003\AppData\Local\Programs\Python\Python314\python.exe"
$Python = if (Test-Path $FixedPython) { $FixedPython } else { "python" }
$OutLog = Join-Path $PSScriptRoot "backend.out.log"
$ErrLog = Join-Path $PSScriptRoot "backend.err.log"
$PidFile = Join-Path $PSScriptRoot "backend.pid"

function Get-RunningPid {
    if (Test-Path $PidFile) {
        $pid0 = [int](Get-Content $PidFile -Raw).Trim()
        if (Get-Process -Id $pid0 -ErrorAction SilentlyContinue) { return $pid0 }
    }
    $procs = Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue
    foreach ($q in $procs) {
        if ($q.CommandLine -match "uvicorn" -and $q.CommandLine -match "--port $Port") { return [int]$q.ProcessId }
    }
    return $null
}

if ($Stop) {
    $pid0 = Get-RunningPid
    if ($pid0) { Stop-Process -Id $pid0 -Force; Remove-Item $PidFile -ErrorAction SilentlyContinue; Write-Host "????? (PID $pid0)" }
    else { Write-Host "?????????" }
    exit 0
}

if (Get-RunningPid) { Write-Host "???????????? -Stop?"; exit 0 }

$argList = @("-m","uvicorn","app.main:app","--host",$HostAddr,"--port","$Port","--log-level","warning")
if ($Reload) { $argList += "--reload" }

Write-Host "????????Ctrl+C ???????????????? $OutLog"
while ($true) {
    $p = Start-Process -FilePath $Python -ArgumentList $argList -WorkingDirectory $BackendDir `
        -RedirectStandardOutput $OutLog -RedirectStandardError $ErrLog -WindowStyle Hidden -PassThru
    Set-Content -Path $PidFile -Value $p.Id
    Write-Host ("[{0}] ?? PID={1} ???" -f (Get-Date -Format "HH:mm:ss"), $p.Id)
    $p.WaitForExit()
    Write-Host ("[{0}] ?????? exit={1}?2s ?????..." -f (Get-Date -Format "HH:mm:ss"), $p.ExitCode)
    Start-Sleep -Seconds 2
}
