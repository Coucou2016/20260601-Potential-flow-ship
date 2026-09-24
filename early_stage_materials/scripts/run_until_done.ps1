#Requires -Version 5.1
# Loop download_all.ps1 until no pending/failed (except paywall) or max rounds.
$ErrorActionPreference = 'Continue'
$ScriptDir = $PSScriptRoot
$Base = Split-Path $ScriptDir -Parent
$StatePath = Join-Path $Base '_download_state.json'
$MaxRounds = 20
$Round = 0

while ($Round -lt $MaxRounds) {
    $Round++
    Write-Host "=== Round $Round / $MaxRounds ==="
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $ScriptDir 'download_all.ps1')
    if (-not (Test-Path $StatePath)) { break }
    $state = Get-Content $StatePath -Raw -Encoding UTF8 | ConvertFrom-Json
    $retry = $state.items | Where-Object { $_.status -in @('pending','failed') }
    if (-not $retry -or $retry.Count -eq 0) {
        Write-Host "No pending/failed items. Done."
        break
    }
    Write-Host "Retry $($retry.Count) items in 60s..."
    Start-Sleep -Seconds 60
}

Write-Host "Final state: $StatePath"
