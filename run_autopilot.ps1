# Script PowerShell de lancement du Moteur Autonome
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "   LANCEMENT DU MOTEUR 100% AUTONOME AUTO-CONSUMABLES (PowerShell)   " -ForegroundColor Green
Write-Host "======================================================================" -ForegroundColor Cyan

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -Path $ScriptDir

python src/autonomous_daemon.py --interval 6
