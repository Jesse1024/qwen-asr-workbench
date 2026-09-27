# Qwen3-ASR Workbench updater + GPU torch installer (logic)
$ErrorActionPreference = 'Continue'
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$index = Join-Path $dir 'app\index.html'
$repo = 'Jesse1024/qwen-asr-workbench'

Write-Host '=============================================='
Write-Host '  Qwen3-ASR Workbench - updater'
Write-Host '=============================================='

if (-not (Test-Path $index)) {
  Write-Host 'app\index.html not found next to this script.'
  exit 1
}
$content = Get-Content $index -Raw
$localVer = ''
if ($content -match 'app-version[^0-9]*([0-9][0-9.]*)') { $localVer = $Matches[1] }
if (-not $localVer) { Write-Host 'Cannot read local version.'; exit 1 }

try {
  $latest = Invoke-RestMethod -Uri "https://api.github.com/repos/$repo/releases/latest" -Headers @{ 'User-Agent' = 'qwen-asr-updater' } -TimeoutSec 25
} catch {
  Write-Host "Failed to reach GitHub: $($_.Exception.Message)"
  exit 1
}
$remoteVer = $latest.tag_name -replace '^v', ''

function IsNewer($a, $b) {
  $A = @(($a -replace '^v','').Split('.'))
  $B = @(($b -replace '^v','').Split('.'))
  for ($i = 0; $i -lt 3; $i++) {
    $ai = 0; if ($A.Count -gt $i) { $ai = [int]$A[$i] }
    $bi = 0; if ($B.Count -gt $i) { $bi = [int]$B[$i] }
    if ($ai -ne $bi) { return $ai -gt $bi }
  }
  return $false
}

Write-Host ''
Write-Host "Current: v$localVer    Latest: v$remoteVer"

if (-not (IsNewer $remoteVer $localVer)) {
  Write-Host 'Already up to date.'
} else {
  $url = "https://raw.githubusercontent.com/$repo/v$remoteVer/app/index.html"
  $srv = "https://raw.githubusercontent.com/$repo/v$remoteVer/server.py"
  Write-Host "Downloading v$remoteVer ..."
  try {
    Invoke-WebRequest -Uri $url -OutFile $index -UseBasicParsing -TimeoutSec 120
    Invoke-WebRequest -Uri $srv -OutFile (Join-Path $dir 'server.py') -UseBasicParsing -TimeoutSec 120
    Write-Host "Updated to v$remoteVer. Restart the workbench to apply."
  } catch {
    Write-Host "Download failed: $($_.Exception.Message)"
  }
}

# GPU torch upgrade (idempotent): NVIDIA users get cu129 build, others keep CPU
Write-Host ''
Write-Host 'Checking NVIDIA GPU for torch upgrade ...'
$nvidia = Get-CimInstance Win32_VideoController | Where-Object { $_.Name -match 'NVIDIA' }
$venvPy = Join-Path $dir '.venv\Scripts\python.exe'
if ($nvidia -and (Test-Path $venvPy)) {
  Write-Host 'NVIDIA GPU detected. Installing CUDA torch (about 3 GB) ...'
  & $venvPy -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu129 --force-reinstall
  if ($LASTEXITCODE -eq 0) { Write-Host 'CUDA torch installed. GPU mode enabled.' }
} else {
  Write-Host 'No NVIDIA GPU found, keeping CPU torch.'
}
