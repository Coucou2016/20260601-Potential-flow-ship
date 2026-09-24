$log = Join-Path $PSScriptRoot 'env_check.log'
function L($m){ Add-Content $log "[$(Get-Date -Format o)] $m" -Encoding UTF8; Write-Output $m }
Remove-Item $log -Force -ErrorAction SilentlyContinue
L '=== env check ==='
L (git --version 2>&1 | Out-String).Trim()
L (curl --version 2>&1 | Select-Object -First 1 | Out-String).Trim()
L "where curl: $(where.exe curl 2>&1 | Out-String)".Trim()
L "where git: $(where.exe git 2>&1 | Out-String)".Trim()
if ($env:HTTP_PROXY) { L "HTTP_PROXY=$env:HTTP_PROXY" }
if ($env:HTTPS_PROXY) { L "HTTPS_PROXY=$env:HTTPS_PROXY" }
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
foreach ($u in @('https://github.com','https://trid.trb.org')) {
  L "--- curl -I $u ---"
  $out = & curl.exe -I -L --max-time 30 --ssl-no-revoke $u 2>&1 | Out-String
  L ($out.Substring(0,[Math]::Min(500,$out.Length)))
}
