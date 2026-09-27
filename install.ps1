# Qwen3-ASR Workbench installer (logic; install.bat calls this)
# English comments only (PS 5.1 GBK pitfall). Chinese output is fine.
$ErrorActionPreference = 'Continue'
$src = Split-Path -Parent $MyInvocation.MyCommand.Path
$dest = Join-Path $env:LOCALAPPDATA 'QwenASR'
$desktop = [Environment]::GetFolderPath('Desktop')

Write-Host '=============================================='
Write-Host '  Qwen3-ASR Workbench - installer'
Write-Host '=============================================='
Write-Host ''

# [0/5] check python
$py = $null
foreach ($c in @('python', 'py')) {
  try { $v = & $c --version 2>$null; if ($v -match '3\.') { $py = $c; break } } catch {}
}
if (-not $py) {
  Write-Host '[0/5] Python 3.10+ not found. Install from https://www.python.org/downloads/'
  Write-Host '      (check "Add python.exe to PATH" during install), then run install.bat again.'
  exit 1
}
Write-Host "[0/5] Found Python: $(& $py --version)"

# [1/5] copy app files
Write-Host "[1/5] Copying files to $dest ..."
New-Item -ItemType Directory -Force -Path $dest | Out-Null
Copy-Item (Join-Path $src 'server.py') (Join-Path $dest 'server.py') -Force
New-Item -ItemType Directory -Force -Path (Join-Path $dest 'app') | Out-Null
Copy-Item (Join-Path $src 'app\index.html') (Join-Path $dest 'app\index.html') -Force
if (Test-Path (Join-Path $src 'app\icon.ico')) {
  Copy-Item (Join-Path $src 'app\icon.ico') (Join-Path $dest 'app\icon.ico') -Force
}
foreach ($u in @('update.bat','update.ps1','uninstall.bat','uninstall.ps1','download-model.bat','download-model.ps1','工作台.bat')) {
  if (Test-Path (Join-Path $src $u)) { Copy-Item (Join-Path $src $u) (Join-Path $dest $u) -Force }
}

# [2/5] create venv with uv (fast) or fallback to venv+pip
$venv = Join-Path $dest '.venv'
$venvPy = Join-Path $venv 'Scripts\python.exe'
if (-not (Test-Path $venvPy)) {
  Write-Host '[2/5] Creating virtual environment ...'
  $uv = Get-Command uv -ErrorAction SilentlyContinue
  if ($uv) {
    & uv venv $venv --python 3.12
  } else {
    & $py -m venv $venv
  }
  if (-not (Test-Path $venvPy)) { Write-Host 'venv creation failed.'; exit 1 }
} else {
  Write-Host '[2/5] Virtual environment already exists, skip.'
}

# [3/5] install deps (CPU torch first for bootstrapping; GPU torch via download-model.ps1)
Write-Host '[3/5] Installing Python dependencies (qwen-asr, modelscope, imageio-ffmpeg) ...'
$pipArgs = @('-m','pip','install','qwen-asr','modelscope','imageio-ffmpeg')
& $venvPy @pipArgs
if ($LASTEXITCODE -ne 0) { Write-Host 'pip install failed.'; exit 1 }
# torch cpu (small, works everywhere; GPU users upgrade in step 4)
& $venvPy -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
if ($LASTEXITCODE -ne 0) { Write-Host 'torch install failed.'; exit 1 }

# [4/5] download model
Write-Host '[4/5] Downloading ASR model (~4.7 GB, from ModelScope, China direct) ...'
& $venvPy -m modelscope download --model Qwen/Qwen3-ASR-1.7B --local_dir (Join-Path $dest 'models\Qwen3-ASR-1.7B')
if ($LASTEXITCODE -ne 0) {
  Write-Host 'Model download failed. Run download-model.bat later to retry.'
}

# [5/5] desktop shortcut
Write-Host '[5/5] Creating desktop shortcut ...'
$lnkPath = Join-Path $desktop '语音转写工作台.lnk'
$ws = New-Object -ComObject WScript.Shell
$lnk = $ws.CreateShortcut($lnkPath)
$lnk.TargetPath = (Join-Path $dest '工作台.bat')
$lnk.WorkingDirectory = $dest
$ico = Join-Path $dest 'app\icon.ico'
if (Test-Path $ico) { $lnk.IconLocation = $ico }
$lnk.Description = 'Qwen3-ASR 本地语音转写 · 南山怪客'
$lnk.Save()

Write-Host ''
Write-Host 'Install complete. Double-click the desktop shortcut to start.'
Write-Host 'Note: CPU-only torch installed. For NVIDIA GPU speed-up run download-model.bat again'
Write-Host '      (it upgrades torch to CUDA build automatically).'
