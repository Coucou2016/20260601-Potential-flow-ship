# Sync _download_state.json ok status from files on disk
$Base = Split-Path $PSScriptRoot -Parent
$StatePath = Join-Path $Base '_download_state.json'
$state = Get-Content $StatePath -Raw -Encoding UTF8 | ConvertFrom-Json

function Test-ValidFile($path) {
    if (-not (Test-Path $path)) { return $false }
    $fi = Get-Item $path
    if ($fi.PSIsContainer) { return (Test-Path (Join-Path $path '.git')) }
    if ($fi.Length -lt 200) { return $false }
    if ($path -match '\.pdf$') {
        $b = Get-Content $path -Encoding Byte -TotalCount 4 -EA SilentlyContinue
        return ($b -and $b[0] -eq 37 -and $b[1] -eq 80)
    }
    if ($path -match '\.zip$') { return $fi.Length -gt 1024 }
    return $true
}

foreach ($item in $state.items) {
    if (-not $item.local_path) { continue }
    if (Test-ValidFile $item.local_path) {
        $item.status = 'ok'
        if (-not $item.local_path -match '\.git') {
            $item.bytes = (Get-Item $item.local_path).Length
        }
        $item.last_error = ''
    }
}
$state.updated = Get-Date -Format 'o'
$state | ConvertTo-Json -Depth 10 | Set-Content $StatePath -Encoding UTF8
$state.items | Group-Object status | ForEach-Object { Write-Host "$($_.Name): $($_.Count)" }
