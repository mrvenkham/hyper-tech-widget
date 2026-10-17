# COSMO laptop brain: lets your phone use the laptop's GPU (RTX 5070) for COSMO.
#
# 1. Install Ollama for Windows first: https://ollama.com/download
# 2. Right-click PowerShell > "Run as administrator", then run:
#      Set-ExecutionPolicy -Scope Process Bypass; .\setup-laptop.ps1
#    Optional: choose a model, e.g.  .\setup-laptop.ps1 -Model llama3.1:8b
#
# Laptop RTX 5070 GPUs have 8 GB of video memory, so 7-8B models are the sweet spot.
# On a 12 GB card you can try gemma3:12b.

param([string]$Model = "qwen2.5:7b")

$ErrorActionPreference = "Stop"
function Say($t) { Write-Host "[COSMO] $t" -ForegroundColor Cyan }

if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
  Say "Ollama isn't installed. Get it from https://ollama.com/download, then run this again."
  exit 1
}

# Listen on the local network, not just this laptop.
Say "Letting Ollama accept connections from your phone..."
[Environment]::SetEnvironmentVariable("OLLAMA_HOST", "0.0.0.0:11434", "User")
$env:OLLAMA_HOST = "0.0.0.0:11434"

# Allow it through the firewall on PRIVATE networks only (your home Wi-Fi),
# never on public Wi-Fi like cafes or school.
if (-not (Get-NetFirewallRule -DisplayName "Ollama for COSMO" -ErrorAction SilentlyContinue)) {
  New-NetFirewallRule -DisplayName "Ollama for COSMO" -Direction Inbound -Protocol TCP -LocalPort 11434 -Action Allow -Profile Private | Out-Null
}
Say "Firewall: allowed on private networks only."

# Restart Ollama so it picks up the new setting.
Get-Process "ollama*" -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep 2
$app = Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama app.exe"
if (Test-Path $app) { Start-Process $app } else { Start-Process ollama -ArgumentList "serve" -WindowStyle Hidden }
Start-Sleep 5

Say "Downloading $Model (a few GB, once)..."
ollama pull $Model

# The address the phone needs is on the adapter that has a router (default gateway):
# your Wi-Fi or cable. Virtual adapters (VirtualBox, Hyper-V, VPNs) have none.
$ip = (Get-NetIPConfiguration |
  Where-Object { $_.IPv4DefaultGateway -ne $null -and $_.NetAdapter.Status -eq "Up" } |
  Select-Object -First 1).IPv4Address.IPAddress
if (-not $ip) { $ip = "<your Wi-Fi IPv4 address from ipconfig>" }

$netCategory = (Get-NetConnectionProfile | Select-Object -First 1).NetworkCategory
if ($netCategory -ne "Private") {
  Say "Your Wi-Fi is marked '$netCategory'. Set it to Private (Settings > Network > Wi-Fi > your network > Private) or the phone can't connect."
}

Write-Host ""
Say "Done. On your phone, in Termux, type:"
Write-Host "    cosmo laptop $ip $Model" -ForegroundColor Green
Write-Host ""
Say "Keep the laptop awake and on the same Wi-Fi as the phone. When it's off, COSMO falls back to the phone model."
