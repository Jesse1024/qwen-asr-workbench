# Qwen3-ASR Workbench uninstaller (logic)
$ErrorActionPreference = 'Continue'
$dest = Join-Path $env:LOCALAPPDATA 'QwenASR'
$desktop = [Environment]::GetFolderPath('Desktop')
$lnk = Join-Path $desktop '语音转写工作台.lnk'

Write-Host '=============================================='
Write-Host '  Qwen3-ASR Workbench - uninstaller'
Write-Host '=============================================='
Write-Host ''

# stop server if running
$conn = Get-NetTCPConnection -LocalPort 8321 -State Listen -ErrorAction SilentlyContinue
if ($conn) {
  Write-Host 'Stopping running server ...'
  Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue
}

$removed = $false
if (Test-Path $lnk) {
  Remove-Item $lnk -Force
  Write-Host '[1/2] Removed desktop shortcut.'
  $removed = $true
} else {
  Write-Host '[1/2] No desktop shortcut found.'
}
if (Test-Path $dest) {
  Remove-Item $dest -Recurse -Force
  Write-Host '[2/2] Removed install folder (including model).'
  $removed = $true
} else {
  Write-Host '[2/2] No install folder found.'
}
Write-Host ''
if ($removed) { Write-Host 'Uninstall complete.' } else { Write-Host 'Nothing to remove.' }
