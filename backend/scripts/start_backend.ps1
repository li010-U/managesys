# 启动/停止 uvicorn 后端服务的守护脚本
# 用法：
#   powershell -ExecutionPolicy Bypass -File scripts\start_backend.ps1           # 前台运行，按 Ctrl+C 停止
#   powershell -ExecutionPolicy Bypass -File scripts\start_backend.ps1 -Stop     # 停止后端
# 参数： -Reload (uvicorn --reload 开发热重载)  -Port 8000  -Host 127.0.0.1
param(
    [switch]$Stop,
    [switch]$Reload,
    [int]$Port = 8000,
    [string]$HostAddr = "127.0.0.1"
)

$ErrorActionPreference = "Stop"
$BackendDir = Split-Path -Parent $PSScriptRoot
$RepoRoot   = Split-Path -Parent $BackendDir
$VenvPy     = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$FixedPython = "C:\Users\34003\AppData\Local\Programs\Python\Python314\python.exe"
$Python = if (Test-Path $VenvPy) { $VenvPy } elseif (Test-Path $FixedPython) { $FixedPython } else { "python" }
$OutLog = Join-Path $PSScriptRoot "backend.out.log"
$ErrLog = Join-Path $PSScriptRoot "backend.err.log"
$PidFile = Join-Path $PSScriptRoot "backend.pid"

# ---- 注入环境变量 ----
# 因 Windows 计划任务通过 User 级 env 传参，并避免交互式外壳
# uvicorn 进程虽可读 .env，但设此确保在 Shell 外亦能生效
$keyFromUser = [Environment]::GetEnvironmentVariable("DEEPSEEK_API_KEY", "User")
if (-not [string]::IsNullOrEmpty($keyFromUser) -and -not $env:DEEPSEEK_API_KEY) {
    $env:DEEPSEEK_API_KEY = $keyFromUser
}
if (-not $env:DATABASE_URL) {
    $dbFromUser = [Environment]::GetEnvironmentVariable("DATABASE_URL", "User")
    if (-not [string]::IsNullOrEmpty($dbFromUser)) { $env:DATABASE_URL = $dbFromUser }
}

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
    if ($pid0) { Stop-Process -Id $pid0 -Force; Remove-Item $PidFile -ErrorAction SilentlyContinue; Write-Host "已停止后端 (PID $pid0)" }
    else { Write-Host "未发现运行中的后端" }
    exit 0
}

if (Get-RunningPid) { Write-Host "后端已在运行，如需停止请加 -Stop"; exit 0 }

$argList = @("-m","uvicorn","app.main:app","--host",$HostAddr,"--port","$Port","--log-level","warning")
if ($Reload) { $argList += "--reload" }

Write-Host "后台守护模式，Ctrl+C 可中断，日志见 $OutLog"
function Test-Database {
    # 说明：当 DATABASE_URL 指向 postgres，用 pg_isready 检测就绪
    if ($env:DATABASE_URL -match "postgres|postgresql") {
        $pgIsReady = Get-Command pg_isready -ErrorAction SilentlyContinue
        if ($pgIsReady) { return (& pg_isready -h 127.0.0.1 -p 5433 -d managesys_prod 2>$null).ExitCode -eq 0 }
        # 若无 pg_isready，则检测 5433 端口连通性
        return [bool](Test-NetConnection -ComputerName 127.0.0.1 -Port 5433 -InformationLevel Quiet -WarningAction SilentlyContinue)
    }
    return $true
}

while ($true) {
    $p = Start-Process -FilePath $Python -ArgumentList $argList -WorkingDirectory $BackendDir `
        -RedirectStandardOutput $OutLog -RedirectStandardError $ErrLog -WindowStyle Hidden -PassThru
    Set-Content -Path $PidFile -Value $p.Id
    Write-Host ("[{0}] 启动 PID={1} 成功" -f (Get-Date -Format "HH:mm:ss"), $p.Id)
    $p.WaitForExit()
    Write-Host ("[{0}] 进程退出 exit={1}，2s 后重启..." -f (Get-Date -Format "HH:mm:ss"), $p.ExitCode)
    # 仅 DB 可达时快速重启 (PG 场景) ; 若 DB 不可达则放缓探测
    if (Test-Database) {
        Start-Sleep -Seconds 2
    } else {
        # DB 不可达时，等待 20s 后再重启，避免空转
        Write-Host ("[{0}] DB 不可达，等待 20s 后重试" -f (Get-Date -Format "HH:mm:ss"))
        Start-Sleep -Seconds 20
    }
}
