#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Autonomous Daemon Runner for Auto-Consumables Agent
===================================================
Orchestre l'exécution 100% autonome et continue du générateur :
- Exécution périodique programmable (par défaut toutes les 6 heures)
- Découverte IA via Gemini 2.5 Flash ou pool haute précision de secours
- Surveillance des rappels officiels RappelConso
- Rendu statique des 12 portails linguistiques (FR, EN, ES, DE, IT, NL, PL, PT, SV, JA, ZH, AR)
- Diffusion multi-canaux Mégaphone IA (Telegra.ph, README GitHub, IndexNow, Archive.org)
- Synchronisation Git automatique optionnelle (push direct)
- Gestion robuste des erreurs avec reprise automatique sans plantage
"""

import argparse
import datetime
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

# Forcer l'encodage UTF-8 sur Windows
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Chemins de base
BASE_DIR = Path(__file__).resolve().parent.parent
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOGS_DIR / "autopilot_daemon.log"

# Configuration du logging double (console + fichier tournant)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ],
)
logger = logging.getLogger("AutonomousDaemon")

# Import du moteur principal
sys.path.insert(0, str(BASE_DIR / "src"))
from agent_engine import run_agent_engine


def run_git_sync(commit_message: str = "chore(autopilot): cycle autonome d'enrichissement du catalogue [skip ci]"):
    """Synchronise automatiquement les modifications locales vers le dépôt GitHub distant."""
    try:
        logger.info("Synchronisation Git automatique en cours...")
        # 1. git add
        subprocess.run(
            ["git", "add", "README.md", "docs/", "data/catalog_state.json", "syndication/"],
            cwd=BASE_DIR,
            check=True,
            capture_output=True,
            text=True,
        )

        # 2. Vérifier s'il y a des changements
        diff_res = subprocess.run(
            ["git", "diff", "--staged", "--quiet"],
            cwd=BASE_DIR,
            capture_output=True,
        )
        if diff_res.returncode == 0:
            logger.info("Aucune modification de fichier à synchroniser sur Git.")
            return

        # 3. git commit
        commit_res = subprocess.run(
            ["git", "commit", "-m", commit_message],
            cwd=BASE_DIR,
            check=True,
            capture_output=True,
            text=True,
        )
        logger.info(f"Commit créé avec succès : {commit_res.stdout.splitlines()[0] if commit_res.stdout else 'OK'}")

        # 4. git pull --rebase & git push
        subprocess.run(["git", "pull", "--rebase", "origin", "main"], cwd=BASE_DIR, capture_output=True)
        push_res = subprocess.run(
            ["git", "push", "origin", "main"],
            cwd=BASE_DIR,
            check=True,
            capture_output=True,
            text=True,
        )
        logger.info("Push vers 'origin main' terminé avec succès.")

    except subprocess.CalledProcessError as err:
        logger.warning(f"Avertissement lors de la synchronisation Git : {err.stderr or err.stdout or err}")
    except Exception as exc:
        logger.warning(f"Erreur imprévue lors de la synchronisation Git : {exc}")


def execute_cycle(cycle_number: int, auto_push: bool = True):
    """Exécute un cycle autonome complet de bout en bout."""
    start_time = time.time()
    logger.info("=" * 70)
    logger.info(f"🚀 DÉMARRAGE DU CYCLE AUTONOME #{cycle_number} - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 70)

    try:
        # Exécution du moteur d'enrichissement + rendu + broadcast
        run_agent_engine()

        # Synchronisation Git si demandée
        if auto_push:
            run_git_sync(f"chore(autopilot): enrichissement autonome cycle #{cycle_number} [skip ci]")

        duration = round(time.time() - start_time, 2)
        logger.info(f"✅ CYCLE #{cycle_number} TERMINÉ AVEC SUCCÈS en {duration}s.")

    except Exception as exc:
        logger.error(f"❌ Échec lors du cycle #{cycle_number} : {exc}", exc_info=True)
        logger.info("Le démon reste actif et retentera au prochain cycle programmé.")


def run_daemon(interval_hours: float = 6.0, auto_push: bool = True):
    """Boucle infinie autonome avec intervalle programmable."""
    interval_seconds = int(interval_hours * 3600)
    logger.info("=" * 70)
    logger.info("🤖 DÉMON AUTONOME AUTO-CONSUMABLES INITIALISÉ")
    logger.info(f"Intervalle configuré : {interval_hours} heure(s) ({interval_seconds} secondes)")
    logger.info(f"Synchronisation Git automatique : {'ACTIVÉE' if auto_push else 'DÉSACTIVÉE'}")
    logger.info("Arrêt possible à tout moment via Ctrl+C")
    logger.info("=" * 70)

    cycle_count = 1
    while True:
        execute_cycle(cycle_number=cycle_count, auto_push=auto_push)

        next_run = datetime.datetime.now() + datetime.timedelta(seconds=interval_seconds)
        logger.info(f"💤 Mise en veille. Prochain cycle prévu à : {next_run.strftime('%Y-%m-%d %H:%M:%S')}...")
        cycle_count += 1

        try:
            time.sleep(interval_seconds)
        except KeyboardInterrupt:
            logger.info("🛑 Signal d'interruption reçu. Arrêt propre du démon.")
            break


def main():
    parser = argparse.ArgumentParser(description="Démon 100% autonome pour l'Agent Consommables.")
    parser.add_argument("--once", action="store_true", help="Exécute un seul cycle complet et quitte.")
    parser.add_argument("--interval", type=float, default=6.0, help="Intervalle entre chaque cycle en heures (défaut : 6h).")
    parser.add_argument("--no-push", action="store_true", help="Désactive le push Git automatique à la fin du cycle.")

    args = parser.parse_args()

    if args.once:
        execute_cycle(cycle_number=1, auto_push=not args.no_push)
    else:
        run_daemon(interval_hours=args.interval, auto_push=not args.no_push)


if __name__ == "__main__":
    main()
