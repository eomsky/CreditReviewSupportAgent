$ErrorActionPreference = 'Stop'
$pocRoot = Split-Path $PSScriptRoot -Parent
$pocPython = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'
$pocTunnel = Join-Path $pocRoot 'workspace\bin\cloudflared.exe'
$pocConfig = Join-Path $pocRoot 'workspace\poc-tunnel.yml'
$pocLogs = Join-Path $pocRoot 'workspace\domain-logs'
foreach ($pocFile in @($pocPython, $pocTunnel, $pocConfig)) {
    if (-not (Test-Path -LiteralPath $pocFile)) { throw "Required file missing: $pocFile" }
}
New-Item -ItemType Directory -Path $pocLogs -Force | Out-Null
foreach ($pocServer in @(@{Port=8766; Script='business_report_test.py'; Name='app'}, @{Port=8767; Script='poc_domain_gateway.py'; Name='gateway'})) {
    if (-not (Get-NetTCPConnection -LocalPort $pocServer.Port -State Listen -ErrorAction SilentlyContinue)) {
        Start-Process -FilePath $pocPython -ArgumentList @('-u', ('"scripts\' + $pocServer.Script + '"')) -WorkingDirectory $pocRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $pocLogs ($pocServer.Name+'.out.log')) -RedirectStandardError (Join-Path $pocLogs ($pocServer.Name+'.err.log')) | Out-Null
    }
}
$pocRunning = Get-CimInstance Win32_Process -Filter "Name='cloudflared.exe'" | Where-Object { $_.CommandLine -match 'poc-tunnel\.yml' }
if (-not $pocRunning) {
    Start-Process -FilePath $pocTunnel -ArgumentList @('tunnel','--config','"workspace\poc-tunnel.yml"','run','credit-review-poc') -WorkingDirectory $pocRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $pocLogs 'tunnel.out.log') -RedirectStandardError (Join-Path $pocLogs 'tunnel.err.log') | Out-Null
}
Write-Output 'POC services started. URL: https://knbaipoc.co.kr'
if (-not (Get-NetTCPConnection -LocalPort 8768 -State Listen -ErrorAction SilentlyContinue)) {
    Start-Process -FilePath $pocPython -ArgumentList @('-u','scripts\generation_performance.py') -WorkingDirectory $pocRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $pocLogs 'performance.out.log') -RedirectStandardError (Join-Path $pocLogs 'performance.err.log') | Out-Null
}
Write-Output 'Keep this PC and the Colab runtime running during demonstrations.'
