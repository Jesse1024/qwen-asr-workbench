# Model download / GPU torch installer (logic)
$ErrorActionPreference = 'Continue'
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvPy = Join-Path $dir '.venv\Scripts\python.exe'
if (-not (Test-Path $venvPy)) {
  Write-Host 'Virtual environment not found. Run install.bat first.'
  exit 1
}

# 1. GPU torch if NVIDIA present, else CPU torch
$nvidia = Get-CimInstance Win32_VideoController | Where-Object { $_.Name -match 'NVIDIA' }
if ($nvidia) {
  $gpuName = ($nvidia | Select-Object -First 1).Name
  Write-Host "NVIDIA GPU detected: $gpuName"
  Write-Host 'Installing CUDA build of PyTorch (~3 GB download) ...'
  & $venvPy -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu129 --force-reinstall
} else {
  Write-Host 'No NVIDIA GPU detected, installing CPU build of PyTorch ...'
  & $venvPy -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
}
if ($LASTEXITCODE -ne 0) { Write-Host 'torch install failed.'; exit 1 }

# 2. model download
Write-Host ''
Write-Host 'Downloading Qwen3-ASR-1.7B model (~4.7 GB, ModelScope direct) ...'
& $venvPy -m modelscope download --model Qwen/Qwen3-ASR-1.7B --local_dir (Join-Path $dir 'models\Qwen3-ASR-1.7B')
if ($LASTEXITCODE -eq 0) {
  Write-Host 'Model ready. Double-click the desktop shortcut to start.'
} else {
  Write-Host 'Download failed. Check network and run download-model.bat again.'
}
