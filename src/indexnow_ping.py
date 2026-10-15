"""Module d'indexation instantanée IndexNow pour moteurs de recherche.

Ce script notifie immédiatement l'API IndexNow (partagée par Bing, Yahoo, Yandex,
DuckDuckGo, Ecosia, Qwant, etc.) de la publication de nouvelles pages.
"""

import logging
import os
import sys
import urllib.parse
from typing import List
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("IndexNowPing")


def ensure_indexnow_key_file(docs_dir: str, indexnow_key: str) -> str:
    """Crée le fichier de vérification de propriété de domaine requis par IndexNow."""
    os.makedirs(docs_dir, exist_ok=True)
    key_file_path = os.path.join(docs_dir, f"{indexnow_key}.txt")
    if not os.path.exists(key_file_path):
        with open(key_file_path, "w", encoding="utf-8") as f:
            f.write(indexnow_key)
        logger.info(f"Fichier de clé IndexNow créé : {key_file_path}")
    return key_file_path


def ping_indexnow(site_base_url: str, url_list: List[str], indexnow_key: str = None) -> bool:
    """Envoie un ping au protocole IndexNow pour référencer la liste des URLs."""
    if not url_list:
        logger.info("Aucune URL à soumettre à IndexNow.")
        return True

    # Clé IndexNow (au moins 8 caractères hexadécimaux / alphanumériques)
    key = indexnow_key or os.getenv("INDEXNOW_KEY", "7b9d64f028e14674a9844c3569bf12a1")

    # Extraire l'hôte du site_base_url
    parsed = urllib.parse.urlparse(site_base_url)
    host = parsed.netloc or parsed.path.split("/")[0]
    if not host or host == "example.com":
        logger.warning(f"Hôte '{host}' non public : simulation de ping IndexNow sans envoi réseau.")
        return True

    key_location = f"{site_base_url.rstrip('/')}/{key}.txt"

    payload = {
        "host": host,
        "key": key,
        "keyLocation": key_location,
        "urlList": url_list,
    }

    endpoint = "https://api.indexnow.org/indexnow"
    logger.info(f"Envoi du ping IndexNow ({len(url_list)} URLs) vers {endpoint}...")

    try:
        response = requests.post(endpoint, json=payload, headers={"Content-Type": "application/json; charset=utf-8"}, timeout=10)
        # Codes acceptés par IndexNow : 200 (OK), 202 (Accepted)
        if response.status_code in [200, 202]:
            logger.info(f"IndexNow : Succès ({response.status_code}) pour {len(url_list)} URL(s).")
            return True
        else:
            logger.warning(f"IndexNow : Réponse inattendue ({response.status_code}) : {response.text}")
            return False
    except Exception as exc:
        logger.error(f"Échec de connexion vers IndexNow : {exc}")
        return False


if __name__ == "__main__":
    test_urls = ["https://example.com/index.html"]
    ping_indexnow("https://example.com", test_urls)
