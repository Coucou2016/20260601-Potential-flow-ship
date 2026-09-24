#Requires -Version 5.1
param(
    [string]$MaterialsRoot = (Split-Path $PSScriptRoot -Parent),
    [string]$CondaEnvPath = "",
    [ValidateSet("hybrid-auto-engine","vlm-auto-engine","vlm-http-client","hybrid-http-client","pipeline")]
    [string]$Backend = "hybrid-auto-engine",
    [int]$MaxFiles = 0,
    [switch]$Resume
)
$CondaEnvPath = if ($CondaEnvPath) { $CondaEnvPath } else { Join-Path $MaterialsRoot ".conda-mineru" }
$mineru = Join-Path $CondaEnvPath "Scripts\mineru.exe"
if (-not (Test-Path $mineru)) { $mineru = "mineru" }
$ParsedRoot = Join-Path $MaterialsRoot "parsed_markdown"
$LogFile = Join-Path $MaterialsRoot "mineru_convert.log"
$env:MINERU_MODEL_SOURCE = if ($env:MINERU_MODEL_SOURCE) { $env:MINERU_MODEL_SOURCE } else { "modelscope" }
function Write-Log($msg) { $line = "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $msg"; Add-Content $LogFile $line -Encoding UTF8; Write-Host $line }
New-Item -ItemType Directory -Force -Path $ParsedRoot | Out-Null
$ext = @(".pdf",".docx",".pptx",".xlsx")
$files = Get-ChildItem $MaterialsRoot -Recurse -File | Where-Object { $ext -contains $_.Extension.ToLowerInvariant() -and $_.FullName -notmatch 'parsed_markdown|\.conda-mineru' } | Sort-Object FullName
if ($MaxFiles -gt 0) { $files = $files | Select-Object -First $MaxFiles }
$ok=0;$fail=0;$skip=0
foreach ($f in $files) {
  $rel = $f.FullName.Substring($MaterialsRoot.Length).TrimStart('\','/')
  $relDir = Split-Path $rel -Parent
  $outDir = if ($relDir) { Join-Path $ParsedRoot $relDir } else { $ParsedRoot }
  if ($Resume -and (Get-ChildItem $outDir -Filter "*.md" -Recurse -ErrorAction SilentlyContinue | Where-Object { $_.BaseName -eq $f.BaseName })) { $skip++; Write-Log "SKIP $rel"; continue }
  New-Item -ItemType Directory -Force -Path $outDir | Out-Null
  Write-Log "CONVERT $rel"
  & $mineru -p $f.FullName -o $outDir -b $Backend 2>&1 | ForEach-Object { Write-Log "  $_" }
  if ($LASTEXITCODE -eq 0) { $ok++ } else { $fail++ }
}
Write-Log "DONE total=$($files.Count) ok=$ok fail=$fail skip=$skip"
