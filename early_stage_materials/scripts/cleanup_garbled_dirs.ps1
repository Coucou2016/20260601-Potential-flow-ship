# Move any files from garbled Chinese-named folders into early_stage_materials, then remove empty dirs.
$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$Target = Join-Path $Root 'early_stage_materials'
if (-not (Test-Path $Target)) { New-Item -ItemType Directory -Path $Target | Out-Null }

Get-ChildItem $Root -Directory | Where-Object {
    $_.Name -ne 'early_stage_materials' -and $_.Name -notmatch '^[a-zA-Z0-9_.-]+$'
} | ForEach-Object {
    $src = $_.FullName
    Write-Host "Migrating from: $($_.Name)"
    Get-ChildItem $src -Recurse -File -ErrorAction SilentlyContinue | ForEach-Object {
        $rel = $_.FullName.Substring($src.Length).TrimStart('\')
        $dest = Join-Path $Target $rel
        $destDir = Split-Path $dest -Parent
        if (-not (Test-Path $destDir)) { New-Item -ItemType Directory -Force -Path $destDir | Out-Null }
        if (-not (Test-Path $dest)) {
            Copy-Item $_.FullName $dest -Force
            Write-Host "  copied: $rel"
        }
    }
    if ((Get-ChildItem $src -Recurse -ErrorAction SilentlyContinue | Measure-Object).Count -eq 0) {
        Remove-Item $src -Recurse -Force -ErrorAction SilentlyContinue
    }
}
