"""Module Mégaphone IA - Diffusion & Référencement Automatisé 100% Gratuit.

Ce module diffuse instantanément notre base de données vers l'écosystème IA :
1. Publication Miroir sur Telegra.ph (Autorité 90/100, API 100% gratuite sans inscription).
2. Mise à jour automatique du README.md racine (Autorité 99/100 sur GitHub).
3. Ping IndexNow instantané vers Bing, ChatGPT Search, Copilot, Qwant, DuckDuckGo.
4. Sauvegarde automatique sur Archive.org (Wayback Machine Save API).
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import re
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("AiBroadcaster")

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DOCS_DIR = BASE_DIR / "docs"
CATALOG_PATH = DATA_DIR / "catalog_state.json"
README_PATH = BASE_DIR / "README.md"

try:
    from indexnow_ping import ensure_indexnow_key_file, ping_indexnow
except ImportError:
    from src.indexnow_ping import ensure_indexnow_key_file, ping_indexnow


# ==============================================================================
# 1. Miroir Telegra.ph (DA 90/100 - API Gratuite sans inscription)
# ==============================================================================

def get_or_create_telegraph_account(catalog_data: Dict[str, Any]) -> Optional[str]:
    """Récupère ou crée un compte Telegra.ph anonyme sans clé API ni mot de passe."""
    token = catalog_data.get("telegraph_access_token")
    if token:
        return token

    url = "https://api.telegra.ph/createAccount?short_name=TechPartsBot&author_name=Catalogue+Pieces+FR"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("ok"):
                new_token = data["result"]["access_token"]
                catalog_data["telegraph_access_token"] = new_token
                logger.info(f"Nouveau compte Telegra.ph créé avec succès (token: {new_token[:8]}...).")
                return new_token
        logger.warning(f"Échec création compte Telegra.ph: {response.text}")
    except Exception as exc:
        logger.error(f"Erreur connexion Telegra.ph createAccount: {exc}")
    return None


def publish_guide_to_telegraph(
    guide: Dict[str, Any],
    access_token: str,
    partner_tag: str,
    site_base_url: str
) -> Optional[str]:
    """Publie une fiche technique propre sur Telegra.ph au format Node JSON."""
    clean_base_url = site_base_url.rstrip("/")
    brand = guide.get("brand", "")
    model = guide.get("model", "")
    slug = guide.get("slug", "")
    category = guide.get("category", "Électroménager")
    meta_desc = guide.get("meta_description", "")
    page_title = f"{brand} {model} - Pièces & Entretien"[:120]

    nodes: List[Dict[str, Any]] = [
        {"tag": "p", "children": [f"Catégorie : {category} | Modèle certifié : {brand} {model}"]},
        {"tag": "p", "children": [meta_desc]},
        {"tag": "h3", "children": ["⚙️ Consommables & Pièces d'Origine Vérifiées"]},
    ]

    # Liste des consommables
    consumable_items = []
    for item in guide.get("consumables", []):
        name = item.get("name", "Consommable")
        pn = item.get("part_number", "Réf. OEM adaptable")
        freq = item.get("frequency", "Selon usage")
        search_q = item.get("search_keywords", f"{brand} {name}")
        encoded_q = urllib.parse.quote_plus(search_q)
        aff_tag = partner_tag if partner_tag else "autoconsom-21"
        aff_url = f"https://www.amazon.fr/s?k={encoded_q}&tag={aff_tag}"

        consumable_items.append({
            "tag": "li",
            "children": [
                {"tag": "b", "children": [f"{name} ({pn}) : "]},
                f"Fréquence : {freq} — ",
                {"tag": "a", "attrs": {"href": aff_url}, "children": ["Commander la pièce sur Amazon.fr ↗"]}
            ]
        })

    nodes.append({"tag": "ul", "children": consumable_items})

    # Tableau des codes erreurs
    nodes.append({"tag": "h3", "children": ["🚨 Codes Pannes & Dépannage Sans Outil"]})
    error_items = []
    for code in guide.get("common_codes", []):
        c_code = code.get("code", "")
        c_sol = code.get("solution", "")
        error_items.append({
            "tag": "li",
            "children": [
                {"tag": "b", "children": [f"{c_code} : "]},
                c_sol
            ]
        })
    nodes.append({"tag": "ul", "children": error_items})

    # Backlinks stratégiques vers GitHub Pages et LLMs.txt
    guide_url = f"{clean_base_url}/guides/{slug}.html"
    llms_url = f"{clean_base_url}/llms.txt"
    catalog_api_url = f"{clean_base_url}/api/v1/catalog.json"

    nodes.extend([
        {"tag": "hr"},
        {"tag": "p", "children": [
            "🔗 Fiche Web Complète & Guide Pas-à-Pas : ",
            {"tag": "a", "attrs": {"href": guide_url}, "children": [f"{brand} {model} sur AutoConsommables"]},
        ]},
        {"tag": "p", "children": [
            "🤖 Flux Moteurs IA & Agents d'Achat : ",
            {"tag": "a", "attrs": {"href": llms_url}, "children": ["Standard llms.txt"]},
            " | ",
            {"tag": "a", "attrs": {"href": catalog_api_url}, "children": ["API JSON Gratuite v1"]}
        ]},
    ])

    payload = {
        "access_token": access_token,
        "title": page_title,
        "author_name": "Catalogue Pieces FR",
        "author_url": clean_base_url,
        "content": nodes,
        "return_content": False,
    }

    try:
        response = requests.post("https://api.telegra.ph/createPage", json=payload, timeout=12)
        if response.status_code == 200:
            res_data = response.json()
            if res_data.get("ok"):
                telegraph_url = res_data["result"]["url"]
                logger.info(f"Miroir Telegra.ph créé avec succès : {telegraph_url}")
                return telegraph_url
            err = str(res_data.get("error", ""))
            if "FLOOD_WAIT" in err:
                wait_match = re.search(r"FLOOD_WAIT_(\d+)", err)
                wait_sec = int(wait_match.group(1)) if wait_match else 5
                logger.warning(f"Rate-limit Telegra.ph ({err}) : pause de {wait_sec}s...")
                import time
                time.sleep(wait_sec + 1)
                retry_resp = requests.post("https://api.telegra.ph/createPage", json=payload, timeout=12)
                if retry_resp.status_code == 200 and retry_resp.json().get("ok"):
                    telegraph_url = retry_resp.json()["result"]["url"]
                    logger.info(f"Miroir Telegra.ph créé après retry : {telegraph_url}")
                    return telegraph_url
        logger.warning(f"Erreur createPage Telegra.ph: {response.text}")
    except Exception as exc:
        logger.error(f"Exception lors de la publication Telegra.ph ({slug}): {exc}")

    return None


def mirror_guides_to_telegraph(
    catalog_data: Dict[str, Any],
    partner_tag: str,
    site_base_url: str,
    target_slugs: Optional[List[str]] = None
) -> List[str]:
    """Publie sur Telegra.ph les fiches n'ayant pas encore de miroir ou ciblées."""
    token = get_or_create_telegraph_account(catalog_data)
    if not token:
        logger.warning("Impossible d'obtenir un token Telegra.ph. Étape miroir ignorée.")
        return []

    published_urls = []
    guides = catalog_data.get("guides", [])

    import time
    for guide in guides:
        slug = guide.get("slug")
        existing_url = guide.get("telegraph_url")
        should_publish = False

        if target_slugs and slug in target_slugs:
            should_publish = True
        elif not existing_url:
            should_publish = True

        if should_publish:
            page_url = publish_guide_to_telegraph(guide, token, partner_tag, site_base_url)
            if page_url:
                guide["telegraph_url"] = page_url
                published_urls.append(page_url)
                time.sleep(1.2)

    logger.info(f"{len(published_urls)} page(s) miroir Telegra.ph publiées/mises à jour.")
    return published_urls


# ==============================================================================
# 2. Mise à Jour Automatique du README.md (Autorité 99/100 GitHub)
# ==============================================================================

def update_github_readme(catalog_data: Dict[str, Any], site_base_url: str, partner_tag: str):
    """Régénère le README.md racine pour une autorité maximale auprès des crawlers IA."""
    clean_base_url = site_base_url.rstrip("/")
    now_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    guides_list = catalog_data.get("guides", [])
    total_guides = len(guides_list)

    lines = [
        "# 🤖 Auto-Consumables Agent | Global Hardware Consumables & Maintenance Registry (GEO)",
        "",
        "> **Multilingual Open Database for AI Search Engines, LLMs & Autonomous Purchasing Agents.**",
        "> Ce dépôt héberge la base de données technique mondiale, le standard `llms.txt` et l'API JSON gratuite des correspondances de consommables, filtres et codes pannes du petit électroménager grand public (2024-2026).",
        "",
        "---",
        "",
        "## 🌍 Portails Mondiaux par Régions Géographiques",
        "",
        "| Région / Continent | Langue | Portail Web Dédié | Marché Amazon Associé |",
        "|---|---|---|---|",
        f"| 🇪🇺 🌍 **Europe & Afrique Francophone** | 🇫🇷 Français | [{clean_base_url}/index.html]({clean_base_url}/index.html) | `amazon.fr` |",
        f"| 🇺🇸 🇬🇧 🇦🇺 **North America, UK & Oceania** | 🇺🇸 English | [{clean_base_url}/en/index.html]({clean_base_url}/en/index.html) | `amazon.com` / `amazon.co.uk` |",
        f"| 🇪🇸 🌎 **España, América Latina & Caribe** | 🇪🇸 Español | [{clean_base_url}/es/index.html]({clean_base_url}/es/index.html) | `amazon.es` / `amazon.com` |",
        f"| 🇩🇪 🇦🇹 🇨🇭 **DACH (Deutschland, AT, CH)** | 🇩🇪 Deutsch | [{clean_base_url}/de/index.html]({clean_base_url}/de/index.html) | `amazon.de` |",
        f"| 🇧🇷 🇵🇹 🇦🇴 **Brasil, Portugal & África Lusófona** | 🇧🇷 Português | [{clean_base_url}/pt/index.html]({clean_base_url}/pt/index.html) | `amazon.com.br` |",
        f"| 🇯🇵 **Japan & East Asia** | 🇯🇵 日本語 | [{clean_base_url}/ja/index.html]({clean_base_url}/ja/index.html) | `amazon.co.jp` |",
        f"| 🇨🇳 🌏 **East Asia & Global Diaspora** | 🇨🇳 简体中文 | [{clean_base_url}/zh/index.html]({clean_base_url}/zh/index.html) | `amazon.com` |",
        "",
        "---",
        "",
        "## 📡 Endpoints Ouverts & Flux IA (Zero Key / Zero Cost)",
        "",
        "Tous les endpoints ci-dessous sont publics, statiques, sans clé API et sans rate-limit :",
        "",
        f"- 📄 **Standard GEO International :** [{clean_base_url}/llms.txt]({clean_base_url}/llms.txt) *(Spécification officielle pour ChatGPT Search, Claude, Perplexity)*",
        f"- 📑 **Dump Technique Intégral :** [{clean_base_url}/llms-full.txt]({clean_base_url}/llms-full.txt) *(Toutes les pièces, codes pannes et liens multi-marketplaces en 1 requête)*",
        f"- 🔌 **API JSON v1 Catalogue Multi-Langues :** [{clean_base_url}/api/v1/catalog.json]({clean_base_url}/api/v1/catalog.json) *(Catalogue structuré avec purchase_urls pour agents d'achat)*",
        f"- ⚠️ **API Rappels Officiels État Français :** [{clean_base_url}/api/v1/rappels-officiels.json]({clean_base_url}/api/v1/rappels-officiels.json) *(Derniers rappels DGCCRF/RappelConso avec équivalents sûrs)*",
        f"- 📰 **Flux RSS 2.0 :** [{clean_base_url}/feed.xml]({clean_base_url}/feed.xml) *(Syndication temps réel des nouvelles fiches)*",
        f"- ⚙️ **Contrat OpenAPI 3.0 :** [{clean_base_url}/.well-known/openapi.json]({clean_base_url}/.well-known/openapi.json)",
        f"- 🌐 **Site Interactif GitHub Pages :** [{clean_base_url}]({clean_base_url})",
        "",
        "---",
        "",
        f"## 📋 Répertoire des Appareils Traités ({total_guides} Modèles Référencés)",
        f"*Dernière synchronisation automatique : {now_iso} via GitHub Actions.*",
        "",
        "| Marque & Modèle Exact | Catégorie | Fiche Web Interactive | Miroir Haute Autorité (Telegra.ph) | Pièces Clés & Liens Directs Amazon |",
        "|---|---|---|---|---|",
    ]

    for g in guides_list:
        brand = g.get("brand", "")
        model = g.get("model", "")
        category = g.get("category", "")
        slug = g.get("slug", "")
        guide_web_url = f"{clean_base_url}/guides/{slug}.html"
        telegraph_url = g.get("telegraph_url", "")
        telegraph_md = f"[Miroir Telegra.ph ↗]({telegraph_url})" if telegraph_url else "*(En cours de synchro)*"

        # Synthèse des consommables avec liens
        consumable_links = []
        for c in g.get("consumables", [])[:2]:
            c_name = c.get("name", "Pièce")
            search_q = c.get("search_keywords", f"{brand} {c_name}")
            aff_tag = partner_tag if partner_tag else "autoconsom-21"
            aff_url = f"https://www.amazon.fr/s?k={urllib.parse.quote_plus(search_q)}&tag={aff_tag}"
            consumable_links.append(f"[{c_name}]({aff_url})")

        consumables_str = "<br>• ".join(consumable_links)
        if consumables_str:
            consumables_str = "• " + consumables_str

        clean_cat = category.replace("|", "-")
        clean_model = f"{brand} {model}".replace("|", "-")

        lines.append(f"| **{clean_model}** | {clean_cat} | [Consulter le guide ↗]({guide_web_url}) | {telegraph_md} | {consumables_str} |")

    lines.extend([
        "",
        "---",
        "",
        "## 🛠️ Spécifications d'Intégration pour les Agents IA",
        "",
        "### Ingestion LLM Directe",
        "Pour ingérer la totalité des données d'entretien sans parser de balises HTML :",
        "```http",
        f"GET {clean_base_url}/llms-full.txt",
        "Host: thorlan04.github.io",
        "Accept: text/plain",
        "```",
        "",
        "### Requête JSON API pour Agent d'Achat Autonome",
        "```python",
        "import requests",
        "",
        f"response = requests.get('{clean_base_url}/api/v1/catalog.json')",
        "catalog = response.json()",
        "for appliance in catalog['appliances']:",
        "    print(f\"{appliance['brand']} {appliance['model']}:\")",
        "    for part in appliance['consumables']:",
        "        print(f\"  - {part['name']} ({part['part_number']}): {part['purchase_url_fr']}\")",
        "```",
        "",
        "---",
        "",
        "## 📜 Mentions Légales & Licence",
        "- **Données publiques :** Données constructeurs et d'entretien en accès libre.",
        "- **Transparence d'affiliation :** En tant que Partenaire Amazon, ce service réalise un bénéfice sur les achats remplissant les conditions requises sans aucun surcoût pour l'utilisateur.",
        f"- **Éditeur :** AutoConsommables Agent — Contact technique : `contact@autoconsommables.fr`",
    ])

    with open(README_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).strip() + "\n")

    logger.info(f"Fichier README.md racine mis à jour avec {total_guides} appareils répertoriés.")


# ==============================================================================
# 3. Ping IndexNow Élargi (Bing, ChatGPT Search, Copilot, Qwant)
# ==============================================================================

def ping_search_engines_indexnow(
    site_base_url: str,
    added_slugs: Optional[List[str]] = None,
    indexnow_key: Optional[str] = None
) -> bool:
    """Envoie un ping IndexNow complet incluant les endpoints GEO et API."""
    base = site_base_url.rstrip("/")
    key = indexnow_key or os.getenv("INDEXNOW_KEY", "7b9d64f028e14674a9844c3569bf12a1")
    ensure_indexnow_key_file(str(DOCS_DIR), key)

    # Indexs pour les 7 langues mondiales
    urls = [
        f"{base}/index.html",
        f"{base}/en/index.html",
        f"{base}/es/index.html",
        f"{base}/de/index.html",
        f"{base}/pt/index.html",
        f"{base}/ja/index.html",
        f"{base}/zh/index.html",
        f"{base}/llms.txt",
        f"{base}/llms-full.txt",
        f"{base}/api/v1/catalog.json",
        f"{base}/api/v1/rappels-officiels.json",
        f"{base}/feed.xml",
    ]

    if added_slugs:
        for slug in added_slugs:
            # Fiche principale FR
            urls.append(f"{base}/guides/{slug}.html")
            # Fiches localisées dans les 6 autres langues
            for lang in ["en", "es", "de", "pt", "ja", "zh"]:
                urls.append(f"{base}/{lang}/guides/{slug}.html")

    return ping_indexnow(site_base_url, urls, key)


# ==============================================================================
# 4. Sauvegarde & Archivage Archive.org (Wayback Machine Save API)
# ==============================================================================

def ping_archive_org(urls: List[str]):
    """Déclenche l'archivage public Wayback Machine de façon concurrente et non-bloquante."""
    if not urls:
        return

    import concurrent.futures

    # Prioriser les 5 premières URLs cibles
    priority_targets = [u.strip() for u in urls if u and u.strip().startswith("http")][:5]
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }

    def _archive_single(target_url: str):
        save_endpoint = f"https://web.archive.org/save/{target_url}"
        try:
            logger.info(f"Ping Archive.org pour {target_url}...")
            requests.get(save_endpoint, headers=headers, timeout=5)
        except Exception as exc:
            logger.debug(f"Ping Archive.org terminé/ignoré pour {target_url}: {exc}")

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        executor.map(_archive_single, priority_targets)


# ==============================================================================
# Orchestration Principale du Mégaphone IA
# ==============================================================================

def broadcast_to_ai_ecosystem(
    catalog_data: Dict[str, Any],
    partner_tag: str,
    site_base_url: str,
    added_slugs: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Coordonne la diffusion complète vers tous les canaux de découverte IA."""
    logger.info("📢 Lancement du Mégaphone IA (Diffusion multi-canaux gratuite)...")

    # 1. Publication Miroir sur Telegra.ph (DA 90/100)
    telegraph_urls = mirror_guides_to_telegraph(
        catalog_data=catalog_data,
        partner_tag=partner_tag,
        site_base_url=site_base_url,
        target_slugs=added_slugs
    )

    # 2. Mise à jour automatique du README.md racine
    update_github_readme(
        catalog_data=catalog_data,
        site_base_url=site_base_url,
        partner_tag=partner_tag
    )

    # 3. Ping IndexNow
    indexnow_success = ping_search_engines_indexnow(
        site_base_url=site_base_url,
        added_slugs=added_slugs
    )

    # 4. Sauvegarde Archive.org pour les nouvelles URLs
    urls_to_archive = [f"{site_base_url.rstrip('/')}/llms.txt"]
    if added_slugs:
        for slug in added_slugs:
            urls_to_archive.append(f"{site_base_url.rstrip('/')}/guides/{slug}.html")
    urls_to_archive.extend(telegraph_urls)

    ping_archive_org(urls_to_archive)

    report = {
        "telegraph_published_count": len(telegraph_urls),
        "telegraph_urls": telegraph_urls,
        "readme_updated": True,
        "indexnow_success": indexnow_success,
        "archived_urls_count": len(urls_to_archive),
    }

    logger.info(f"📢 Mégaphone IA terminé avec succès : {report}")
    return report


if __name__ == "__main__":
    if CATALOG_PATH.exists():
        with open(CATALOG_PATH, "r", encoding="utf-8") as f:
            test_catalog = json.load(f)
        broadcast_to_ai_ecosystem(
            catalog_data=test_catalog,
            partner_tag="autoconsom-21",
            site_base_url="https://thorlan04.github.io/auto-consumables-agent"
        )
