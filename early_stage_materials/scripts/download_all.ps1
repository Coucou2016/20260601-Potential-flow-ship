#Requires -Version 5.1
<#
.SYNOPSIS
  Resumable bulk download for early_stage_materials (_download_state.json).
.USAGE
  powershell -ExecutionPolicy Bypass -File early_stage_materials\scripts\download_all.ps1
#>
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = 'Continue'

[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 -bor [Net.SecurityProtocolType]::Tls13
$ProgressPreference = 'SilentlyContinue'

$Base = Split-Path $PSScriptRoot -Parent
$StatePath = Join-Path $Base '_download_state.json'
$LogPath = Join-Path $Base 'download.log'
$CsvPath = Join-Path $Base 'download_log.csv'

$UnpaywallEmail = 'potential-flow-ship@local.dev'
$MaxAttempts = 8
$BackoffSeconds = @(5, 15, 30, 60, 90, 120, 120, 180, 180, 240, 300, 300)

function Write-Log($msg) {
    $line = "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $msg"
    for ($t = 0; $t -lt 5; $t++) {
        try {
            Add-Content -Path $LogPath -Value $line -Encoding UTF8 -ErrorAction Stop
            break
        } catch {
            Start-Sleep -Milliseconds (200 * ($t + 1))
        }
    }
    Write-Host $line
}

function Get-State {
    if (Test-Path $StatePath) {
        return Get-Content $StatePath -Raw -Encoding UTF8 | ConvertFrom-Json
    }
    return @{ items = @(); version = 1; updated = (Get-Date -Format 'o') }
}

function Save-State($state) {
    $state.updated = (Get-Date -Format 'o')
    $state | ConvertTo-Json -Depth 10 | Set-Content $StatePath -Encoding UTF8
}

function Get-ItemState($state, $id) {
    $found = $state.items | Where-Object { $_.id -eq $id }
    if ($found) { return $found }
    $new = [PSCustomObject]@{
        id = $id; url = ''; local_path = ''; status = 'pending'
        bytes = 0; attempts = 0; last_error = ''; alternates_tried = @()
        sha256 = ''; category = ''
    }
    $state.items += $new
    return $new
}

function Test-FileValid($path) {
    if (-not (Test-Path $path)) { return $false }
    $fi = Get-Item $path
    if ($fi.Length -lt 200) { return $false }
    if ($path -match '\.pdf$') {
        $b = Get-Content $path -Encoding Byte -TotalCount 5 -ErrorAction SilentlyContinue
        if (-not $b -or $b.Count -lt 4) { return $false }
        return ([char]$b[0] -eq '%' -and [char]$b[1] -eq 'P')
    }
    if ($path -match '\.(zip|gz)$') { return $fi.Length -gt 1024 }
    return $true
}

function Test-ItemOk($item) {
    if ($item.status -ne 'ok') { return $false }
    if (-not $item.local_path -or -not (Test-Path $item.local_path)) { return $false }
    $fi = Get-Item $item.local_path -ErrorAction SilentlyContinue
    if (-not $fi) { return $false }
    if ($item.bytes -gt 0 -and $fi.Length -ne $item.bytes) { return $false }
    if (-not (Test-FileValid $item.local_path)) { return $false }
    return $true
}

function Get-FileSha256($path) {
    if (-not (Test-Path $path)) { return '' }
    return (Get-FileHash $path -Algorithm SHA256).Hash
}


$Script:MaxItemsPerRun = 9999
$Script:ItemsProcessedThisRun = 0
function Test-RunBudget { return $true }
function Use-RunBudget { $Script:ItemsProcessedThisRun++ }

function Reset-InvalidDownloads($state) {
    foreach ($item in $state.items) {
        if ($item.status -ne 'ok') { continue }
        if ($item.id -match '^code_') { continue }
        if (-not $item.local_path -or -not (Test-Path $item.local_path)) {
            $item.status = 'pending'
            continue
        }
        if ((Get-Item $item.local_path).PSIsContainer) { continue }
        if (-not (Test-FileValid $item.local_path)) {
            Write-Log "RESET invalid file: $($item.id)"
            $item.status = 'pending'
            $item.bytes = 0
            $item.sha256 = ''
            Remove-Item $item.local_path -Force -ErrorAction SilentlyContinue
        }
    }
    Save-State $state
}

function Write-CitationStub($def) {
    if (-not $def.doi) { return }
    $stub = $def.out -replace '\.pdf$', '_citation.txt'
    $dir = Split-Path $stub -Parent
    if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
    @(
        "Title: $($def.id)"
        "DOI: $($def.doi)"
        "Primary URL: $($def.url)"
        "Status: paywalled or manual download required"
        "Alternates tried: see _download_state.json"
        "Try: institutional library, ResearchGate, author page, Unpaywall"
    ) | Set-Content $stub -Encoding UTF8
}

function Invoke-ResumableDownload {
    param([string]$Url, [string]$Out)
    $dir = Split-Path $Out -Parent
    if ($dir -and -not (Test-Path $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
    $args = @('-L', '-C', '-', '--retry', '10', '--retry-delay', '5', '--ssl-no-revoke', '-o', $Out, $Url)
    $curlErr = Join-Path $env:TEMP "curl_err_$([guid]::NewGuid().ToString('N')).txt"
    & curl.exe @args 2> $curlErr | Out-Null
    $ok = $LASTEXITCODE -eq 0
    if (-not $ok -and (Test-Path $curlErr)) {
        $et = Get-Content $curlErr -Raw -ErrorAction SilentlyContinue
        if ($et -match 'byte ranges|Cannot resume' -and (Test-Path $Out)) {
            Remove-Item $Out -Force -ErrorAction SilentlyContinue
            $args = $args | Where-Object { $_ -ne '-C' -and $_ -ne '-' }
            & curl.exe @args 2> $null | Out-Null
            $ok = $LASTEXITCODE -eq 0
        }
    }
    Remove-Item $curlErr -Force -ErrorAction SilentlyContinue
    if ($ok) { Write-Log "curl ok: $Out" }
    return $ok
}
function Download-Resumable {
    param([string]$Url, [string]$Out)
    $dir = Split-Path $Out -Parent
    if ($dir -and -not (Test-Path $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
    $tmp = "$Out.part"
    $curlArgs = @(
        '-L', '--ssl-no-revoke', '--retry', '3', '--retry-delay', '3',
        '--connect-timeout', '45', '--max-time', '900', '-f',
        '-A', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) PotentialFlowShip/1.0',
        '-o', $tmp, $Url
    )
    if ((Test-Path $tmp) -and (Get-Item $tmp).Length -gt 0) { $curlArgs = @('-C', '-') + $curlArgs }
    $webErr = ''
    $curlBin = 'curl.exe'
    if ($Url -match 'neptech\.co|mit\.edu|folk\.ntnu\.no') {
        $msysCurl = 'D:\msys64\usr\bin\curl.exe'
        if (Test-Path $msysCurl) { $curlBin = $msysCurl }
    }
    & $curlBin @curlArgs 2>$null | Out-Null
    if ($LASTEXITCODE -eq 33 -and (Test-Path $tmp)) {
        Remove-Item $tmp -Force -ErrorAction SilentlyContinue
        $curlArgs = $curlArgs | Where-Object { $_ -ne '-C' -and $_ -ne '-' }
        & $curlBin @curlArgs 2>$null | Out-Null
    }
    if ($LASTEXITCODE -eq 0 -and (Test-Path $tmp) -and (Get-Item $tmp).Length -gt 100) {
        Move-Item -Force $tmp $Out
        return @{ ok = $true; bytes = (Get-Item $Out).Length; error = '' }
    }
    try {
        $prev = [System.Net.ServicePointManager]::SecurityProtocol
        [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]::Tls12
        $wc = New-Object System.Net.WebClient
        $wc.Headers.Add('User-Agent', 'Mozilla/5.0 PotentialFlowShip/1.0')
        if (Test-Path $tmp) {
            $existing = (Get-Item $tmp).Length
            $wc.Headers.Add('Range', "bytes=$existing-")
        }
        $wc.DownloadFile($Url, $tmp)
        if ((Test-Path $tmp) -and (Get-Item $tmp).Length -gt 100) {
            Move-Item -Force $tmp $Out
            return @{ ok = $true; bytes = (Get-Item $Out).Length; error = '' }
        }
    } catch {
        $webErr = $_.Exception.Message
    } finally {
        [System.Net.ServicePointManager]::SecurityProtocol = $prev
    }
    return @{ ok = $false; bytes = 0; error = "curl=$LASTEXITCODE; web=$webErr" }
}

function Invoke-WithBackoff {
    param([scriptblock]$Action, [string]$Label)
    $err = ''
    for ($i = 0; $i -lt $MaxAttempts; $i++) {
        try {
            $r = & $Action
            if ($r.ok) { return $r }
            $err = $r.error
        } catch {
            $err = $_.Exception.Message
        }
        $wait = $BackoffSeconds[[Math]::Min($i, $BackoffSeconds.Length - 1)]
        Write-Log "Retry $($i+1)/$MaxAttempts for $Label after ${wait}s: $err"
        Start-Sleep -Seconds $wait
    }
    return @{ ok = $false; error = $err }
}

function Get-UnpaywallPdf($doi) {
    if (-not $doi) { return $null }
    $doi = $doi -replace '^https?://(dx\.)?doi\.org/', ''
    $url = "https://api.unpaywall.org/v2/$doi?email=$UnpaywallEmail"
    try {
        $r = Invoke-RestMethod -Uri $url -TimeoutSec 60
        if ($r.best_oa_location -and $r.best_oa_location.url_for_pdf) { return $r.best_oa_location.url_for_pdf }
        if ($r.best_oa_location -and $r.best_oa_location.url) { return $r.best_oa_location.url }
    } catch { }
    return $null
}

function Get-SemanticScholarPdf($doi) {
    if (-not $doi) { return $null }
    try {
        $r = Invoke-RestMethod -Uri "https://api.semanticscholar.org/graph/v1/paper/DOI:$doi?fields=openAccessPdf,externalIds" -TimeoutSec 60
        if ($r.openAccessPdf -and $r.openAccessPdf.url) { return $r.openAccessPdf.url }
    } catch { }
    return $null
}

function Clone-GitRepo {
    param([string]$Url, [string]$Dest)
    if (Test-Path (Join-Path $Dest '.git')) {
        Push-Location $Dest
        git fetch --depth 1 2>&1 | Out-Null
        Pop-Location
        return @{ ok = $true; bytes = 0; error = '' }
    }
    if (Test-Path $Dest) { Remove-Item -Recurse -Force $Dest -ErrorAction SilentlyContinue }
    $parent = Split-Path $Dest -Parent
    if (-not (Test-Path $parent)) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }
    $out = git clone --depth 1 $Url $Dest 2>&1
    if ($LASTEXITCODE -eq 0) { return @{ ok = $true; bytes = 0; error = '' } }
    return @{ ok = $false; error = ($out | Out-String) }
}

function Process-DownloadItem {
    param($def, $state)
    $item = Get-ItemState $state $def.id
    $item.url = $def.url
    $item.local_path = $def.out
    $item.category = $def.category
    if (Test-ItemOk $item) {
        Write-Log "SKIP ok: $($def.id)"
        return
    }
    $urls = @($def.url) + @($def.mirrors)
    if ($def.doi) {
        $ua = Get-UnpaywallPdf $def.doi
        if ($ua) { $urls += $ua }
        $ss = Get-SemanticScholarPdf $def.doi
        if ($ss) { $urls += $ss }
        $urls += "https://doi.org/$($def.doi)"
    }
    foreach ($alt in @($def.alternates)) { if ($alt) { $urls += $alt } }
    $urls = $urls | Select-Object -Unique
    $ok = $false
    foreach ($u in $urls) {
        if (-not $u) { continue }
        $item.attempts++
        if ($item.alternates_tried -notcontains $u) { $item.alternates_tried += $u }
        Write-Log "GET $($def.id): $u"
        $r = Invoke-WithBackoff { Download-Resumable -Url $u -Out $def.out } -Label $def.id
        if ($r.ok -and (Test-FileValid $def.out)) {
            $item.status = 'ok'
            $item.bytes = (Get-Item $def.out).Length
            $item.sha256 = Get-FileSha256 $def.out
            $item.last_error = ''
            $ok = $true
            break
        }
        $item.last_error = $r.error
    }
    if (-not $ok) {
        if ($def.paywall_expected) {
            $item.status = 'paywall'
            Write-CitationStub $def
        } else { $item.status = 'failed' }
        Write-Log "FAIL $($def.id): $($item.last_error)"
    }
    Save-State $state
}

function Process-GitItem {
    param($def, $state)
    $item = Get-ItemState $state $def.id
    $item.url = $def.url
    $item.local_path = $def.out
    $item.category = $def.category
    if (Test-Path (Join-Path $def.out '.git')) {
        $item.status = 'ok'
        Save-State $state
        Write-Log "SKIP git ok: $($def.id)"
        return
    }
    $item.attempts++
    $r = Invoke-WithBackoff { Clone-GitRepo -Url $def.url -Dest $def.out } -Label $def.id
    if ($r.ok) { $item.status = 'ok'; $item.last_error = '' }
    else { $item.status = 'failed'; $item.last_error = $r.error }
    Save-State $state
}

$L = @{
    hsd = 'literature\high_speed_displacement'
    sd = 'literature\semi_displacement'
    pc = 'literature\planing_craft'
    wwm = 'literature\wind_waves_maneuvering'
    ts = 'literature\textbooks_surveys'
    pf = 'code\potential_flow_seakeeping'
    ps = 'code\planing_semiempirical'
    gnc = 'code\maneuvering_gnc'
    npl = 'data\npl_series'
    kcs = 'data\kcs_benchmark'
    d372 = 'data\delft_372'
}

$Lit = @(
    @{ id='lit_stf_1970'; url='https://trid.trb.org/View/495'; out=(Join-Path $Base "$($L.ts)\STF_1970_TRID495.html"); category='textbooks'; mirrors=@('https://web.archive.org/web/2020/https://trid.trb.org/View/495') }
    @{ id='lit_faltinsen_sea_loads'; url='https://www.osti.gov/biblio/5464335'; out=(Join-Path $Base "$($L.ts)\Faltinsen_Sea_Loads_OSTI.html"); category='textbooks' }
    @{ id='lit_faltinsen_hsmv_preview'; url='https://api.pageplace.de/preview/DT0400.9780511133633_A23689594/preview-9780511133633_A23689594.pdf'; out=(Join-Path $Base "$($L.ts)\Faltinsen_HSMV_preview.pdf"); category='textbooks' }
    @{ id='lit_ma_2005'; doi='10.1016/j.oceaneng.2004.08.012'; url='https://doi.org/10.1016/j.oceaneng.2004.08.012'; out=(Join-Path $Base "$($L.hsd)\Ma_2005_2.5D.pdf"); category='hsd'; paywall_expected=$true }
    @{ id='lit_arribas_2006'; doi='10.1016/j.oceaneng.2005.09.008'; url='https://doi.org/10.1016/j.oceaneng.2005.09.008'; out=(Join-Path $Base "$($L.sd)\Arribas_2006.pdf"); category='sd'; paywall_expected=$true }
    @{ id='lit_kring_1994'; url='https://dspace.mit.edu/bitstream/handle/1721.1/11939/31384162-MIT.pdf?sequence=2&isAllowed=y'; out=(Join-Path $Base "$($L.ts)\Kring_1994_MIT.pdf"); category='textbooks'; mirrors=@(
        'https://web.archive.org/web/2020/https://dspace.mit.edu/bitstream/handle/1721.1/11939/31384162-MIT.pdf?sequence=2&isAllowed=y',
        'https://core.ac.uk/download/pdf/48633506.pdf',
        'http://hdl.handle.net/1721.1/11939'
    ) }
    @{ id='lit_donatini_2022'; doi='10.1016/j.oceaneng.2022.112222'; url='https://doi.org/10.1016/j.oceaneng.2022.112222'; out=(Join-Path $Base "$($L.ts)\Donatini_2022_Capytaine_forward_speed.pdf"); category='textbooks'; paywall_expected=$true }
    @{ id='lit_bailey_npl'; doi='10.1016/S0029-8018(99)00023-4'; url='https://api.semanticscholar.org/graph/v1/paper/search?query=Bailey+NPL+hull&limit=1'; out=(Join-Path $Base "$($L.npl)\Bailey_NPL_metadata.json"); category='npl'; paywall_expected=$true; alternates=@('https://doi.org/10.1016/S0029-8018(99)00023-4') }
    @{ id='lit_mercier_savitsky_1973'; url='https://trid.trb.org/view/14059'; out=(Join-Path $Base "$($L.pc)\Mercier_Savitsky_1973_TRID14059.html"); category='planing' }
    @{ id='lit_compton_1986'; url='https://onepetro.org/mtsn/article-pdf/23/04/345/2199243/sname-mtsn-1986-23-4-345.pdf'; out=(Join-Path $Base "$($L.pc)\Compton_1986_MTSN.pdf"); category='planing'; paywall_expected=$true; alternates=@(
        'https://web.archive.org/web/2019/https://onepetro.org/mtsn/article-pdf/23/04/345/2199243/sname-mtsn-1986-23-4-345.pdf'
    ) }
    @{ id='lit_savitsky_preplaning'; url='https://doi.org/10.1063/1.5143123'; out=(Join-Path $Base "$($L.pc)\Savitsky_preplaning_AIP.pdf"); category='planing'; paywall_expected=$true }
    @{ id='lit_savitsky_1964'; doi='10.5957/atc-1-04-71'; url='https://onepetro.org/MTSN/article/1/04/71/172383/Hydrodynamic-Design-of-Planing-Hulls'; out=(Join-Path $Base "$($L.pc)\Savitsky_1964_planing.html"); category='planing'; mirrors=@('https://web.archive.org/web/2020/https://onepetro.org/MTSN/article/1/04/71/172383/Hydrodynamic-Design-of-Planing-Hulls'); paywall_expected=$false }
    @{ id='lit_fridsma'; url='https://trid.trb.org/view/2061'; out=(Join-Path $Base "$($L.pc)\Fridsma_TRID2061.html"); category='planing' }
    @{ id='lit_savitsky_brown_1976'; url='https://trid.trb.org/View/3500'; out=(Join-Path $Base "$($L.pc)\Savitsky_Brown_1976_TRID.html"); category='planing'; mirrors=@(
        'https://trid.trb.org/view/3500',
        'https://web.archive.org/web/2020/https://trid.trb.org/View/3500'
    ); alternates=@(
        'https://apps.dtic.mil/sti/pdfs/ADA028000.pdf',
        'https://apps.dtic.mil/sti/citations/ADA028000'
    ) }
    @{ id='lit_zhao_water_entry'; url='https://nap.nationalacademies.org/read/5870/chapter/29'; out=(Join-Path $Base "$($L.hsd)\Zhao_water_entry_NAP_ch29.html"); category='hsd' }
    @{ id='lit_sun_faltinsen_2010'; doi='10.2514/1.44717'; url='https://doi.org/10.2514/1.44717'; out=(Join-Path $Base "$($L.pc)\Sun_Faltinsen_2010_planing.pdf"); category='planing'; paywall_expected=$true }
    @{ id='lit_planing_review_2024'; doi='10.1016/j.oceaneng.2024.114383'; url='https://doi.org/10.1016/j.oceaneng.2024.114383'; out=(Join-Path $Base "$($L.pc)\Planing_hull_review_2024.pdf"); category='planing'; paywall_expected=$true; mirrors=@('https://www.sciencedirect.com/science/article/pii/S0029801824003834') }
    @{ id='lit_fossen_2012'; doi='10.1016/j.oceaneng.2012.09.012'; url='https://doi.org/10.1016/j.oceaneng.2012.09.012'; out=(Join-Path $Base "$($L.wwm)\Fossen_2012_wind_waves.pdf"); category='wwm'; paywall_expected=$true; alternates=@(
        'https://folk.ntnu.no/thomas.fossen/pub/Fossen2012windwaves.pdf',
        'https://folk.ntnu.no/thomas.fossen/pub/Fossen2012wind.pdf',
        'https://www.researchgate.net/profile/Thor-Fossen/publication/257623456_How_to_incorporate_wind_waves_and_ocean_currents_in_the_marine_craft_equations_of_motion/links/0deec53c8c0c5e0e3c000000/How-to-incorporate-wind-waves-and-ocean-currents-in-the-marine-craft-equations-of-motion.pdf'
    ) }
    @{ id='lit_molland_book'; url='https://www.routledge.com/Maritime-Engineering-Ship-Design/Molland/p/book/9780750665275'; out=(Join-Path $Base "$($L.ts)\Molland_Ship_Design_metadata.html"); category='textbooks' }
)

$GitRepos = @(
    @{ id='code_pdstrip'; url='https://github.com/eriove/pdstrip.git'; out=(Join-Path $Base "$($L.pf)\pdstrip"); category='pf' }
    @{ id='code_hams'; url='https://github.com/YingyiLiu/HAMS.git'; out=(Join-Path $Base "$($L.pf)\HAMS"); category='pf' }
    @{ id='code_bemrosetta'; url='https://github.com/BEMRosetta/BEMRosetta.git'; out=(Join-Path $Base "$($L.pf)\BEMRosetta"); category='pf' }
    @{ id='code_ow3d'; url='https://gitlab.gbar.dtu.dk/oceanwave3d/ow3d-seakeeping.git'; out=(Join-Path $Base "$($L.pf)\ow3d-seakeeping"); category='pf' }
    @{ id='code_openplaning'; url='https://github.com/elcf/python-openplaning.git'; out=(Join-Path $Base "$($L.ps)\python-openplaning"); category='ps' }
    @{ id='code_binder_openplaning'; url='https://github.com/elcf/binder-openplaning.git'; out=(Join-Path $Base "$($L.ps)\binder-openplaning"); category='ps' }
    @{ id='code_mmgdynamics'; url='https://github.com/nikpau/mmgdynamics.git'; out=(Join-Path $Base "$($L.gnc)\mmgdynamics"); category='gnc' }
    @{ id='code_shipmmg'; url='https://github.com/ShipMMG/shipmmg.git'; out=(Join-Path $Base "$($L.gnc)\shipmmg"); category='gnc' }
    @{ id='code_nemoh'; url='https://github.com/LHEEA/Nemoh.git'; out=(Join-Path $Base "$($L.pf)\Nemoh"); category='pf' }
    @{ id='code_capytaine'; url='https://github.com/capytaine/capytaine.git'; out=(Join-Path $Base "$($L.pf)\capytaine"); category='pf' }
    @{ id='code_mss_tools'; url='https://github.com/cybergalactic/MSS.git'; out=(Join-Path $Base "$($L.gnc)\MSS"); category='gnc' }
    @{ id='code_python_vehicle'; url='https://github.com/cybergalactic/PythonVehicleSimulator.git'; out=(Join-Path $Base "$($L.gnc)\PythonVehicleSimulator"); category='gnc' }
)

$DataItems = @(
    @{ id='data_kcs_index'; url='https://t2015.nmri.go.jp/kcs.html'; out=(Join-Path $Base "$($L.kcs)\kcs_index.html"); category='kcs' }
    @{ id='data_kcs_hull_zip'; url='https://t2015.nmri.go.jp/file/Geometry_IGES_files/kcs/KCS_hull_SVA.zip'; out=(Join-Path $Base "$($L.kcs)\KCS_hull_SVA.zip"); category='kcs' }
    @{ id='data_kcs_rudder_zip'; url='https://t2015.nmri.go.jp/file/Geometry_IGES_files/kcs/KCS_Rudder.zip'; out=(Join-Path $Base "$($L.kcs)\KCS_Rudder.zip"); category='kcs' }
    @{ id='data_kcs_prop_zip'; url='https://t2015.nmri.go.jp/file/Geometry_IGES_files/kcs/KCS_prop_MOERI.zip'; out=(Join-Path $Base "$($L.kcs)\KCS_prop_MOERI.zip"); category='kcs' }
    @{ id='data_kcs_case211_zip'; url='https://t2015.nmri.go.jp/file/Geometry_IGES_files/kcs/KCS_hull_Case2-11.zip'; out=(Join-Path $Base "$($L.kcs)\KCS_hull_Case2-11.zip"); category='kcs' }
    @{ id='data_delft372_report'; url='https://neptech.co/wp-content/uploads/2025/06/CFD_Report-DELFT_372-Calm-Water-EN.pdf'; out=(Join-Path $Base "$($L.d372)\Delft372_CFD_validation_report.pdf"); category='d372' }
    @{ id='data_delft372_strath'; url='https://strathprints.strath.ac.uk/82218/1/Duman_Bal_OE_2022_Turn_and_zigzag_manoeuvres_of_Delft_catamaran_372_using_CFD_based_system_simulation_method.pdf'; out=(Join-Path $Base "$($L.d372)\Delft372_manoeuvring_CFD_paper.pdf"); category='d372' }
)

function Repair-StatePaths($state) {
    foreach ($item in $state.items) {
        if ($item.local_path -match '前期资料|鏂囩尞|文献\\|代码\\|数据\\') {
            $lp = $item.local_path -replace '\\+', '\'
            $lp = $lp -replace '.*early_stage_materials', $Base
            if ($lp -notmatch [regex]::Escape($Base)) {
                $name = Split-Path $item.local_path -Leaf
                $id = $item.id
                $map = @{
                    'lit_stf_1970' = "$($L.ts)\STF_1970_TRID495.html"
                    'lit_faltinsen_sea_loads' = "$($L.ts)\Faltinsen_Sea_Loads_OSTI.html"
                    'lit_faltinsen_hsmv_preview' = "$($L.ts)\Faltinsen_HSMV_preview.pdf"
                    'lit_ma_2005' = "$($L.hsd)\Ma_2005_2.5D.pdf"
                    'lit_arribas_2006' = "$($L.sd)\Arribas_2006.pdf"
                    'lit_kring_1994' = "$($L.ts)\Kring_1994_MIT.pdf"
                }
                if ($map.ContainsKey($id)) { $lp = Join-Path $Base $map[$id] }
                elseif ($name) {
                    foreach ($def in ($Lit + $DataItems)) {
                        if ($def.id -eq $id) { $lp = $def.out; break }
                    }
                    foreach ($def in $GitRepos) {
                        if ($def.id -eq $id) { $lp = $def.out; break }
                    }
                }
            }
            $item.local_path = $lp
        }
    }
    Save-State $state
}

if (-not (Test-Path $LogPath)) { New-Item -ItemType File -Path $LogPath | Out-Null }
Write-Log "=== download_all.ps1 start (early_stage_materials) ==="
$state = Get-State
Repair-StatePaths $state
$state = Get-State
Reset-InvalidDownloads $state
$state = Get-State
# Retry failed items (reset to pending) unless max attempts exhausted on paywall-only
foreach ($item in $state.items) {
    if ($item.status -eq 'failed' -and $item.attempts -lt 12) {
        $item.status = 'pending'
        Write-Log "RESET failed->pending: $($item.id)"
    }
}
Save-State $state
$state = Get-State

function Save-CitationStub($def, $state) {
    $item = Get-ItemState $state $def.id
    if ($item.status -eq 'ok') { return }
    $stub = ($def.out -replace '\.[^.]+$','') + '_CITATION.txt'
    $lines = @(
        "id: $($def.id)",
        "primary_url: $($def.url)",
        "doi: $($def.doi)",
        "status: $($item.status)",
        "note: Paywalled or manual download required. Try institutional access, authors, or library."
    )
    $lines | Set-Content $stub -Encoding UTF8
}

foreach ($d in $Lit) { Process-DownloadItem $d $state; Save-CitationStub $d $state }
foreach ($g in $GitRepos) { Process-GitItem $g $state }
foreach ($d in $DataItems) { Process-DownloadItem $d $state }

$wheelsDir = Join-Path $Base "$($L.pf)\capytaine_wheels"
if (-not (Test-Path $wheelsDir)) { New-Item -ItemType Directory -Force -Path $wheelsDir | Out-Null }
$wh = Get-ItemState $state 'pip_capytaine'
$wh.local_path = $wheelsDir
$wh.category = 'pf'
if (-not (Test-ItemOk $wh)) {
    $wh.attempts++
    pip download capytaine -d $wheelsDir 2>> $LogPath | Out-Null
    if ((Get-ChildItem $wheelsDir -ErrorAction SilentlyContinue).Count -gt 0) { $wh.status = 'ok' } else { $wh.status = 'failed' }
    Save-State $state
}

$mssDir = Join-Path $Base "$($L.gnc)\fossen_MSS_mirror"
if (-not (Test-Path $mssDir)) { New-Item -ItemType Directory -Force -Path $mssDir | Out-Null }
@(
    @{ id='fossen_mss_index'; url='https://www.fossen.biz/MSS/'; out=(Join-Path $mssDir 'index.html') }
    @{ id='fossen_pvs'; url='https://www.fossen.biz/pythonVehicleSim/'; out=(Join-Path $mssDir 'PythonVehicleSim_index.html') }
) | ForEach-Object { Process-DownloadItem @{ id=$_.id; url=$_.url; out=$_.out; category='gnc' } $state }

$kcsIndex = Join-Path $Base "$($L.kcs)\kcs_index.html"
if (Test-Path $kcsIndex) {
    $html = Get-Content $kcsIndex -Raw -Encoding UTF8
    $links = [regex]::Matches($html, 'href="([^"]+\.(?:dat|zip|pdf|txt|gz))"') | ForEach-Object { $_.Groups[1].Value } | Select-Object -Unique
    $baseUrl = 'https://t2015.nmri.go.jp/'
    foreach ($lnk in $links) {
        $full = if ($lnk -match '^https?://') { $lnk } else { $baseUrl + $lnk.TrimStart('/') }
        $fname = Split-Path $full -Leaf
        $out = Join-Path $Base "$($L.kcs)\$fname"
        $id = "data_kcs_$fname"
        $ki = Get-ItemState $state $id
        if (-not (Test-ItemOk $ki)) {
            Process-DownloadItem @{ id=$id; url=$full; out=$out; category='kcs' } $state
        }
    }
}

$state = Get-State
$rows = foreach ($i in $state.items) {
    [PSCustomObject]@{ id=$i.id; url=$i.url; local_path=$i.local_path; status=$i.status; bytes=$i.bytes; attempts=$i.attempts; last_error=$i.last_error }
}
$rows | Export-Csv $CsvPath -NoTypeInformation -Encoding UTF8

$ok = ($state.items | Where-Object { $_.status -eq 'ok' }).Count
$pay = ($state.items | Where-Object { $_.status -eq 'paywall' }).Count
$fail = ($state.items | Where-Object { $_.status -eq 'failed' }).Count
$pend = ($state.items | Where-Object { $_.status -eq 'pending' }).Count
Write-Log "SUMMARY ok=$ok paywall=$pay failed=$fail pending=$pend"
Write-Host "SUMMARY ok=$ok paywall=$pay failed=$fail pending=$pend"
