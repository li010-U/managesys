<#
.SYNOPSIS
  后端主链路冒烟测试：对运行中的后端做 HTTP 冒烟（登录 + 核心只读接口 + OpenAPI）。
.DESCRIPTION
  用于部署/重启后端后快速验证核心链路是否可用。
  全部通过退出码 0；任一步失败退出码 1（配合守护脚本/CI 使用）。
.PARAMETER BaseUrl
  后端地址，默认 http://127.0.0.1:8000
.PARAMETER Username
  登录用户名，默认 admin
.PARAMETER Password
  登录密码；缺省则读取 $env:SMOKE_PASSWORD
.EXAMPLE
  .\scripts\smoke.ps1 -BaseUrl http://127.0.0.1:8000
#>
param(
    [string]$BaseUrl = "http://127.0.0.1:8000",
    [string]$Username = "admin",
    [string]$Password = $env:SMOKE_PASSWORD
)

$ErrorActionPreference = "Stop"
$fail = 0

function Test-Step {
    param([string]$Name, [scriptblock]$Block)
    try {
        & $Block | Out-Null
        Write-Host ("[OK]   " + $Name) -ForegroundColor Green
    } catch {
        Write-Host ("[FAIL] " + $Name + " : " + $_.Exception.Message) -ForegroundColor Red
        $script:fail = 1
    }
}

# 1) 基本连通 + OpenAPI 文档可生成（曾因缺失 Request 导入而 500）
Test-Step "GET /openapi.json (200)" {
    $r = Invoke-WebRequest -Uri "$BaseUrl/openapi.json" -TimeoutSec 10 -UseBasicParsing
    if ($r.StatusCode -ne 200) { throw "status=$($r.StatusCode)" }
    if ($r.Content -notmatch '"paths"') { throw "no paths in openapi" }
}

# 2) 登录拿 token
$token = $null
Test-Step "POST /api/v1/auth/login (200)" {
    if (-not $Password) { throw "未提供密码(可设 \$env:SMOKE_PASSWORD)" }
    $body = @{ username = $Username; password = $Password } | ConvertTo-Json
    $r = Invoke-RestMethod -Uri "$BaseUrl/api/v1/auth/login" -Method Post -Body $body -ContentType "application/json" -TimeoutSec 10
    if (-not $r.access_token) { throw "no access_token" }
    $script:token = $r.access_token
}
if (-not $token) {
    exit 1
}
$headers = @{ Authorization = "Bearer $token" }

# 3) 核心只读接口
Test-Step "GET /api/v1/facilities/data-centers" {
    $r = Invoke-WebRequest -Uri "$BaseUrl/api/v1/facilities/data-centers" -Headers $headers -TimeoutSec 10 -UseBasicParsing
    if ($r.StatusCode -ne 200) { throw "status=$($r.StatusCode)" }
}
Test-Step "GET /api/v1/facilities/rooms" {
    $r = Invoke-WebRequest -Uri "$BaseUrl/api/v1/facilities/rooms" -Headers $headers -TimeoutSec 10 -UseBasicParsing
    if ($r.StatusCode -ne 200) { throw "status=$($r.StatusCode)" }
}
Test-Step "GET /api/v1/facilities/racks" {
    $r = Invoke-WebRequest -Uri "$BaseUrl/api/v1/facilities/racks" -Headers $headers -TimeoutSec 10 -UseBasicParsing
    if ($r.StatusCode -ne 200) { throw "status=$($r.StatusCode)" }
}
Test-Step "GET /api/v1/alerts/stats" {
    $r = Invoke-WebRequest -Uri "$BaseUrl/api/v1/alerts/stats" -Headers $headers -TimeoutSec 10 -UseBasicParsing
    if ($r.StatusCode -ne 200) { throw "status=$($r.StatusCode)" }
}
Test-Step "GET /api/v1/dashboard/activities" {
    $r = Invoke-WebRequest -Uri "$BaseUrl/api/v1/dashboard/activities" -Headers $headers -TimeoutSec 10 -UseBasicParsing
    if ($r.StatusCode -ne 200) { throw "status=$($r.StatusCode)" }
}
# AI 快照：须含真实功率字段（第⑤项）
Test-Step "GET /api/v1/assistant/snapshot (200)" {
    $r = Invoke-RestMethod -Uri "$BaseUrl/api/v1/assistant/snapshot" -Headers $headers -TimeoutSec 10
    if ($null -eq $r.power) { throw "snapshot missing power block" }
}

if ($fail -eq 0) {
    Write-Host "`nSMOKE OK: 全部主链路接口可用" -ForegroundColor Green
} else {
    Write-Host "`nSMOKE FAIL: 存在失败项" -ForegroundColor Red
}
exit $fail
