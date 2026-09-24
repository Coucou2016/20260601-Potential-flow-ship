[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 -bor [Net.SecurityProtocolType]::Tls13
$ProgressPreference = 'SilentlyContinue'
# Test connectivity, log only
$log = "d:\Projects\20260601-Potential-flow-ship\early_stage_materials\scripts\network_fix.log"
@("https://github.com","https://trid.trb.org","https://www.osti.gov") | ForEach-Object {
  try { $r = Invoke-WebRequest -Uri $_ -Method Head -TimeoutSec 30 -UseBasicParsing; "$_ OK $($r.StatusCode)" } 
  catch { "$_ FAIL $($_.Exception.Message)" }
} | Set-Content $log
