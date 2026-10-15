@echo off
TITLE Auto-Consumables Autopilot Daemon
echo ======================================================================
echo    LANCEMENT DU MOTEUR 100%% AUTONOME AUTO-CONSUMABLES
echo ======================================================================
cd /d "%~dp0"
python src/autonomous_daemon.py --interval 6
pause
