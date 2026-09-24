#Requires -Version 5.1
# One-time migration: 前期资料 (and mojibake subfolders) -> early_stage_materials
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = 'Stop'

$ProjectRoot = 'd:\Projects\20260601-Potential-flow-ship'
$NewBase = Join-Path $ProjectRoot 'early_stage_materials'

$OldBase = Get-ChildItem $ProjectRoot -Directory |
    Sort-Object { (Get-ChildItem $_.FullName -Recurse -File -ErrorAction SilentlyContinue).Count } -Descending |
    Select-Object -First 1
if (-not $OldBase -or (Get-ChildItem $OldBase.FullName -Recurse -File -EA SilentlyContinue).Count -eq 0) {
    throw "No source folder with downloaded content found under $ProjectRoot"
}
$OldBase = $OldBase.FullName
Write-Host "Source: $OldBase"

$dirs = @(
    'literature\high_speed_displacement', 'literature\semi_displacement', 'literature\planing_craft',
    'literature\wind_waves_maneuvering', 'literature\textbooks_surveys',
    'code\potential_flow_seakeeping', 'code\planing_semiempirical', 'code\maneuvering_gnc',
    'data\npl_series', 'data\kcs_benchmark', 'data\delft_372', 'data\other_benchmarks', 'scripts'
)
foreach ($rel in $dirs) {
    $p = Join-Path $NewBase $rel
    if (-not (Test-Path $p)) { New-Item -ItemType Directory -Force -Path $p | Out-Null }
}

$codeMap = @{
    '势流与耐波' = 'code\potential_flow_seakeeping'
    '滑行与半经验' = 'code\planing_semiempirical'
    '操纵与GNC' = 'code\maneuvering_gnc'
}
$dataMap = @{
    'NPL系列' = 'data\npl_series'
    'KCS' = 'data\kcs_benchmark'
    'Delft372' = 'data\delft_372'
    '其他基准' = 'data\other_benchmarks'
}
$litMap = @{
    '01_高速排水船' = 'literature\high_speed_displacement'
    '02_半排水船' = 'literature\semi_displacement'
    '03_滑行艇' = 'literature\planing_craft'
    '04_风浪流与操纵' = 'literature\wind_waves_maneuvering'
    '05_综述与教材' = 'literature\textbooks_surveys'
}

function Move-TreeIfExists($src, $dst) {
    if (-not (Test-Path $src)) { return }
    if (-not (Test-Path $dst)) { New-Item -ItemType Directory -Force -Path $dst | Out-Null }
    $robolog = Join-Path $env:TEMP "migrate_robocopy_$(Get-Random).log"
    & robocopy.exe $src $dst /E /MOVE /R:2 /W:2 /NFL /NDL /NJH /NJS /NP | Out-Null
    if ($LASTEXITCODE -ge 8) {
        Write-Warning "robocopy $src -> $dst exit=$LASTEXITCODE (see $robolog)"
        Get-ChildItem $src -Force -ErrorAction SilentlyContinue | ForEach-Object {
            $target = Join-Path $dst $_.Name
            try {
                if ($_.PSIsContainer) { Move-TreeIfExists $_.FullName $target }
                elseif (-not (Test-Path $target) -or (Get-Item $target).Length -lt $_.Length) {
                    Copy-Item -Force $_.FullName $target
                    Remove-Item -Force $_.FullName -ErrorAction SilentlyContinue
                }
            } catch { Write-Warning $_.Exception.Message }
        }
    }
    if (Test-Path $src) {
        $left = Get-ChildItem $src -Force -ErrorAction SilentlyContinue
        if (-not $left) { Remove-Item $src -Force -Recurse -ErrorAction SilentlyContinue }
    }
}

# Code
$codeRoot = Join-Path $OldBase '代码'
if (-not (Test-Path $codeRoot)) {
    $codeRoot = (Get-ChildItem $OldBase -Directory | Where-Object { $_.Name -match '代码' } | Select-Object -First 1).FullName
}
if ($codeRoot -and (Test-Path $codeRoot)) {
    foreach ($sub in Get-ChildItem $codeRoot -Directory -ErrorAction SilentlyContinue) {
        $rel = $codeMap[$sub.Name]
        if (-not $rel -and $sub.Name -match '势流') { $rel = 'code\potential_flow_seakeeping' }
        if (-not $rel -and $sub.Name -match '滑行') { $rel = 'code\planing_semiempirical' }
        if (-not $rel -and $sub.Name -match 'GNC|操纵') { $rel = 'code\maneuvering_gnc' }
        if ($rel) { Move-TreeIfExists $sub.FullName (Join-Path $NewBase $rel) }
    }
}

# Data
$dataRoot = Join-Path $OldBase '数据'
if (-not (Test-Path $dataRoot)) {
    $dataRoot = (Get-ChildItem $OldBase -Directory | Where-Object { $_.Name -match '数据' } | Select-Object -First 1).FullName
}
if ($dataRoot -and (Test-Path $dataRoot)) {
    foreach ($sub in Get-ChildItem $dataRoot -Directory -ErrorAction SilentlyContinue) {
        $rel = $dataMap[$sub.Name]
        if (-not $rel -and $sub.Name -match 'NPL') { $rel = 'data\npl_series' }
        if (-not $rel -and $sub.Name -eq 'Delft372') { $rel = 'data\delft_372' }
        if (-not $rel -and $sub.Name -match '其他|基准') { $rel = 'data\other_benchmarks' }
        if ($rel) { Move-TreeIfExists $sub.FullName (Join-Path $NewBase $rel) }
    }
}

# Literature (correct Chinese tree)
if (Test-Path (Join-Path $OldBase '文献')) {
    foreach ($sub in Get-ChildItem (Join-Path $OldBase '文献') -Directory -ErrorAction SilentlyContinue) {
        $rel = $litMap[$sub.Name]
        if ($rel) { Move-TreeIfExists $sub.FullName (Join-Path $NewBase $rel) }
    }
}

# Mojibake 文献 folder (UTF-8 misread as Latin-1): 鏂囩尞
Get-ChildItem $OldBase -Directory -ErrorAction SilentlyContinue | Where-Object { $_.Name -match '尞$' -or $_.Name -eq '鏂囩尞' } | ForEach-Object {
    Get-ChildItem $_.FullName -Recurse -File -ErrorAction SilentlyContinue | ForEach-Object {
        $name = $_.Name
        $parent = Split-Path $_.DirectoryName -Leaf
        $destRel = 'literature\textbooks_surveys'
        if ($parent -match '^01' -or $name -match 'Ma_|Zhao_') { $destRel = 'literature\high_speed_displacement' }
        elseif ($parent -match '^02' -or $name -match 'Arribas') { $destRel = 'literature\semi_displacement' }
        elseif ($parent -match '^03' -or $name -match 'Savitsky|Fridsma|Compton|Mercier|Sun_|Planing') { $destRel = 'literature\planing_craft' }
        elseif ($parent -match '^04' -or $name -match 'Fossen') { $destRel = 'literature\wind_waves_maneuvering' }
        elseif ($parent -match '^05' -or $name -match 'STF_|Faltinsen|Kring|Donatini|Molland') { $destRel = 'literature\textbooks_surveys' }
        $dest = Join-Path (Join-Path $NewBase $destRel) $name
        if (-not (Test-Path $dest) -or (Get-Item $dest).Length -lt $_.Length) {
            Move-Item -Force $_.FullName $dest
        }
    }
}

# Root artifacts
foreach ($f in @('download.log', '_download_state.json', 'download_run_console.txt', 'download_log.csv')) {
    $src = Join-Path $OldBase $f
    if (Test-Path $src) {
        $dst = Join-Path $NewBase $f
        if (-not (Test-Path $dst)) { Move-Item -Force $src $dst }
        else { Get-Content $src -Raw -Encoding UTF8 | Add-Content $dst -Encoding UTF8 }
    }
}

# Remove empty duplicate root (20-byte garbled name)
Get-ChildItem $ProjectRoot -Directory | ForEach-Object {
    $fc = (Get-ChildItem $_.FullName -Recurse -File -EA SilentlyContinue | Measure-Object).Count
    if ($fc -eq 0 -and $_.FullName -ne $NewBase) {
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($_.Name)
        if ($bytes.Length -gt 15) {
            Remove-Item $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
            Write-Host "Removed empty duplicate: $($_.Name)"
        }
    }
}

Write-Host "Migration complete -> $NewBase"
