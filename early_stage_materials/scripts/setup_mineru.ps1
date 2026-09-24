#Requires -Version 5.1
param(
    [string]$MaterialsRoot = (Split-Path $PSScriptRoot -Parent),
    [string]$CondaEnvPath = "",
    [switch]$SkipModelDownload
)
$ErrorActionPreference = "Stop"
$CondaEnvPath = if ($CondaEnvPath) { $CondaEnvPath } else { Join-Path $MaterialsRoot ".conda-mineru" }
$LogInstall = Join-Path $MaterialsRoot "mineru_install.log"
function Write-Log($msg) {
    $line = "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $msg"
    Add-Content -Path $LogInstall -Value $line
    Write-Host $line
}
Write-Log "=== setup_mineru.ps1 start ==="
$env:MINERU_MODEL_SOURCE = if ($env:MINERU_MODEL_SOURCE) { $env:MINERU_MODEL_SOURCE } else { "modelscope" }
$env:PIP_INDEX_URL = if ($env:PIP_INDEX_URL) { $env:PIP_INDEX_URL } else { "https://pypi.org/simple" }
$condaExe = "D:\miniforge3\Scripts\conda.exe"
if (-not (Test-Path $CondaEnvPath)) {
    if (-not (Test-Path $condaExe)) { throw "conda not found" }
    & $condaExe create -y -p $CondaEnvPath python=3.12 pip -c conda-forge 2>&1 | Tee-Object -Append $LogInstall
}
$py = Join-Path $CondaEnvPath "python.exe"
& $py -m pip install -U pip wheel 2>&1 | Tee-Object -Append $LogInstall
& $py -m pip install -U "mineru[all]" 2>&1 | Tee-Object -Append $LogInstall
if (-not $SkipModelDownload) {
    $dl = Join-Path $CondaEnvPath "Scripts\mineru-models-download.exe"
    if (Test-Path $dl) { & $dl 2>&1 | Tee-Object -Append $LogInstall }
}
Write-Log "=== setup_mineru.ps1 done ==="
