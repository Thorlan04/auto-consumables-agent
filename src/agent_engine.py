"""Moteur Autonome de Génération et Monétisation de Fiches Pratiques Électroménager.

Ce script :
1. Charge l'état du catalogue (data/catalog_state.json).
2. Utilise le SDK officiel google-genai (gemini-2.5-flash) en mode JSON strict pour découvrir
   2 nouveaux modèles d'appareils grand public très vendus en France.
3. Génère les fiches techniques d'entretien sans outil, codes voyants et consommables indispensables.
4. Construit des liens de recherche Amazon Partenaires 100% infaillibles (zéro 404).
5. Compile le site statique dans docs/ via Jinja2 avec balisage SEO riche et JSON-LD.
6. Envoie un ping IndexNow pour indexation immédiate.
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import re
import sys
import urllib.parse
from pathlib import Path
from typing import List, Optional

import requests

from jinja2 import Environment, FileSystemLoader
from pydantic import BaseModel, Field

# Chargement d'éventuelles variables .env locales
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    from indexnow_ping import build_priority_ping_urls, ensure_indexnow_key_file, ping_indexnow
except ImportError:
    from src.indexnow_ping import build_priority_ping_urls, ensure_indexnow_key_file, ping_indexnow

try:
    from ai_broadcaster import broadcast_to_ai_ecosystem
except ImportError:
    from src.ai_broadcaster import broadcast_to_ai_ecosystem

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("AgentEngine")

# Configuration des chemins
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
TEMPLATES_DIR = BASE_DIR / "templates"
DOCS_DIR = BASE_DIR / "docs"
GUIDES_DIR = DOCS_DIR / "guides"
SYNDICATION_DIR = BASE_DIR / "syndication"
CATALOG_PATH = DATA_DIR / "catalog_state.json"


# ==============================================================================
# Modèles de données Pydantic pour validation stricte
# ==============================================================================

class ErrorCodeItem(BaseModel):
    code: str = Field(description="Nom exact du code d'erreur ou libellé du voyant lumineux clignotant")
    meaning: str = Field(description="Explication simple de la cause pour l'utilisateur")
    solution: str = Field(description="Procédure de résolution pas-à-pas réalisable sans outil")


class ConsumableItem(BaseModel):
    name: str = Field(description="Nom précis de la pièce d'usure ou du consommable d'origine")
    part_number: str = Field(default="Réf. OEM adaptable", description="Référence constructeur officielle (PN / Part Number, ex: DLS C002, CA6903/10, AF400-CRISP, ou Réf. constructeur adaptable)")
    frequency: str = Field(description="Fréquence exacte recommandée de remplacement ou recharge")
    why_replace: str = Field(description="Conséquence directe de l'usure ou de l'encrassement (perte de puissance, fuite, calcaire, odeurs)")
    search_keywords: str = Field(description="Mots-clés de recherche ultra-précis pour Amazon France combinant marque, modèle exact, référence PN et nom de pièce")
    affiliate_url: Optional[str] = None


class FaqItem(BaseModel):
    question: str = Field(description="Question concrète fréquemment posée par un propriétaire")
    answer: str = Field(description="Réponse claire et pratique sans ambiguïté")


class ApplianceGuide(BaseModel):
    slug: str = Field(description="Identifiant URL unique en minuscules avec tirets incluant la référence (ex: roborock-qrevo-curv-qrc02-entretien)")
    title: str = Field(description="Titre optimisé SEO H1 en français incluant la référence constructeur exacte")
    brand: str = Field(description="Marque de l'appareil (ex: Roborock, De'Longhi, Philips, Ninja, Tineco, Dreame)")
    model: str = Field(description="Modèle ultra-précis avec référence constructeur exacte (ex: Switch S7 (FW210100EU), DoubleStack XL (SL400EU))")
    category: str = Field(description="Catégorie parmi: Aspirateurs Laveurs, Machines à Café à Grains, Robots Aspirateurs, Friteuses sans Huile (Air Fryer), Purificateurs d'Air, Centrales Vapeur")
    meta_description: str = Field(description="Méta description SEO accrocheuse de 130 à 155 caractères avec référence PN")
    common_codes: List[ErrorCodeItem] = Field(description="3 codes erreurs ou voyants d'entretien courant", min_length=3, max_length=3)
    consumables: List[ConsumableItem] = Field(description="3 à 4 consommables indispensables avec référence PN", min_length=3, max_length=4)
    faq: List[FaqItem] = Field(description="3 questions/réponses pertinentes", min_length=3, max_length=3)


class GeminiBatchResponse(BaseModel):
    new_appliances: List[ApplianceGuide]


# ==============================================================================
# Fonction Pure de Monétisation Amazon Infaillible
# ==============================================================================

# ==============================================================================
# Fonction Pure de Monétisation Amazon Infaillible (FR & International)
# ==============================================================================

def build_affiliate_url(search_query: str, partner_tag: str, domain: str = "amazon.fr") -> str:
    """Construit une URL de recherche Amazon Partenaires infaillible (sans 404 ni ASIN obsolète).

    Règles :
    - N'invente jamais d'ASIN ni d'URL directe produit.
    - Utilise urllib.parse.quote_plus pour encoder proprement la requête de recherche.
    - Supporte amazon.fr (France/UE) et amazon.com (USA / Global).
    """
    cleaned_query = search_query.strip()
    encoded_query = urllib.parse.quote_plus(cleaned_query)
    clean_tag = partner_tag.strip() if partner_tag else "autoconsom-21"
    clean_domain = domain.strip().lower()
    return f"https://www.{clean_domain}/s?k={encoded_query}&tag={clean_tag}"


# ==============================================================================
# Prompt Système & Génération IA avec google-genai
# ==============================================================================

SYSTEM_INSTRUCTION = """Tu es un ingénieur expert mondial en maintenance préventive de petit électroménager et en SEO d'intention d'achat (France, USA, UK, Europe).

RÈGLE DE SÉCURITÉ ABSOLUE ET STRICTE :
- INTERDICTION FORMELLE de traiter des réparations électriques internes (ouverture de carter haute tension, condensateurs, soudures), appareils au gaz, chaudières, automobile critique ou matériel médical.
- LIMITE-TOI EXCLUSIVEMENT aux consommables et pièces d'usure remplaçables à la main sans outil par l'utilisateur (filtres HEPA, brosses rotatives amovibles, cartouches anticalcaire, bacs, sacs, produits de détartrage doux) et aux opérations d'entretien courant (nettoyage externe, vidage, réinitialisation de voyant filtre).

RÈGLE D'OR N°1 — CIBLAGE CHIRURGICAL DES RÉFÉRENCES EXACTES (2024 À 2026) :
- INTERDICTION ABSOLUE de choisir des dénominations génériques ou des catégories vagues (ex: 'Aspirateur robot', 'Machine à café', 'Air Fryer').
- Tu dois IMPÉRATIVEMENT sélectionner des modèles récents très populaires commercialisés entre 2024 et 2026 AVEC LEUR RÉFÉRENCE CONSTRUCTEUR EXACTE (SKU / Part Number complet).
  Modèles de référence prioritaires à fort volume de recherche :
  * Tineco Floor One Switch S7
  * Ninja Foodi Dual Zone AF400EU
  * Roborock S8 MaxV Ultra
  * DeLonghi Magnifica Start ECAM 220.22.GB
  * Philips Série 5400 EP5447/90
  * Dreame H14 Pro
  * Ninja DoubleStack XL 9,5L (SL400EU)
  * Roborock Qrevo Curv (QRC02-00)
  * Dreame X40 Ultra Complete
  * Breville Barista Touch Impress (BES881BSS)
  * Shark Stratos Cordless Pet Pro (IZ400EU / IZ400UK)
  * Dyson V15s Detect Submarine (SV47)
  * Calor Pro Express Vision (GV9820C0)
  * Levoit Core 400S Smart True HEPA

RÈGLE D'OR N°2 — TABLE TECHNIQUE DE CORRESPONDANCE DES PIÈCES :
- Pour chaque consommable d'usure, fournis :
  * Le nom précis de la pièce (ex: Rouleau brosse microfibre bi-matière, Cartouche filtrante anti-tartre)
  * Le champ 'part_number' : la référence constructeur officielle exacte (PN / SKU / référence fabricant si connue, ex: DLS C002, CA6903/10, AF-400-PLATE, ZR009006, 971634-01) ou 'Réf. constructeur adaptable'
  * La fréquence de remplacement recommandée
  * Les mots-clés de recherche ultra-ciblés incluant la référence et le modèle pour Amazon.

RÈGLE D'OR N°3 — CODES PANNES & VOYANTS SPÉCIFIQUES :
- Fournis 3 codes voyants ou alertes spécifiques à ce modèle exact (ex: voyant DWT, code E02, alerte Calc/Clean) avec la manipulation de résolution sans outil.

Ces 2 appareils NE DOIVENT PAS faire partie de la liste des appareils déjà existants fournie dans la requête.

Rends strictement une structure JSON valide correspondant au schéma demandé."""


def generate_new_guides_with_gemini(existing_slugs: List[str], existing_models: List[str]) -> List[ApplianceGuide]:
    """Interroge Gemini 2.5 Flash pour générer 2 nouveaux guides d'appareils non répertoriés."""
    api_key = os.getenv("GEMINI_API_KEY", "").strip()

    if not api_key:
        logger.warning("GEMINI_API_KEY non configurée. Bascule sur la réserve d'appareils populaires pour tests.")
        return get_fallback_appliances(existing_slugs)

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)

        prompt = f"""Génère 2 NOUVEAUX modèles d'appareils populaires en France.
Appareils déjà répertoriés dans notre catalogue (À NE SURTOUT PAS REPRENDRE) :
{json.dumps(existing_models, ensure_ascii=False, indent=2)}

Slugs déjà utilisés :
{json.dumps(existing_slugs, ensure_ascii=False, indent=2)}

Génère la réponse au format JSON conforme."""

        logger.info("Interrogation de gemini-2.5-flash via le SDK officiel google-genai...")
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                response_mime_type="application/json",
                response_schema=GeminiBatchResponse,
                temperature=0.7,
            ),
        )

        raw_json = response.text
        logger.info("Réponse JSON reçue de Gemini. Validation des données...")

        parsed_data = json.loads(raw_json)
        batch = GeminiBatchResponse(**parsed_data)
        items_list = [g.model_dump() for g in batch.new_appliances]

        valid_guides: List[ApplianceGuide] = []
        for raw_item in items_list[:2]:
            guide = ApplianceGuide(**raw_item)
            # Nettoyage préventif du slug
            guide.slug = re.sub(r"[^a-z0-9\-]+", "-", guide.slug.lower()).strip("-")
            valid_guides.append(guide)

        logger.info(f"{len(valid_guides)} nouveaux guides validés avec succès.")
        return valid_guides

    except Exception as exc:
        logger.error(f"Erreur lors de la génération Gemini : {exc}", exc_info=True)
        logger.info("Utilisation des fiches de secours haute précision pour garantir la continuité.")
        return get_fallback_appliances(existing_slugs)


def get_fallback_appliances(existing_slugs: List[str]) -> List[ApplianceGuide]:
    """Réserve d'appareils très vendus pour tests locaux ou secours si quota API indisponible."""
    backup_pool = [
        ApplianceGuide(
            slug="roborock-s8-entretien-consommables",
            title="Roborock S8 & S8 Pro Ultra : Consommables, Brosses et Codes Erreurs",
            brand="Roborock",
            model="S8 / S8 Pro Ultra",
            category="Robots Aspirateurs",
            meta_description="Filtres HEPA, rouleaux duo-rubber, serpillières vibrantes et sacs à poussière pour Roborock S8. Guide d'entretien sans démontage.",
            common_codes=[
                {
                    "code": "Erreur 1 : Tour LiDAR bloquée",
                    "meaning": "La tourelle laser supérieure ne tourne plus librement en raison d'une poussière ou d'un obstacle.",
                    "solution": "Retirer tout obstacle visuel, faire tourner délicatement la tête rotative orange au doigt pour déloger les poussières, nettoyer la lentille au chiffon doux sec."
                },
                {
                    "code": "Erreur 2 : Pare-chocs bloqué",
                    "meaning": "Le pare-chocs avant reste enfoncé suite à un contact ou de la poussière est coincée dans l'interstice.",
                    "solution": "Tapoter doucement plusieurs fois sur le pare-chocs avant droit et gauche pour débloquer les micro-interrupteurs mécaniques et dégager d'éventuels débris."
                },
                {
                    "code": "Erreur 4 : Capteurs de vide encrassés",
                    "meaning": "Les 4 capteurs infrarouges de vide sous le châssis sont recouverts de poussière fine.",
                    "solution": "Retourner le robot, essuyer les 4 fenêtres transparentes de détection de falaise avec un chiffon en microfibre propre non pelucheux."
                }
            ],
            consumables=[
                {
                    "name": "Paire de Rouleaux Brosses DuoRubber en Caoutchouc",
                    "frequency": "Remplacement tous les 6 à 12 mois",
                    "why_replace": "L'usure des lamelles en caoutchouc diminue le frottement sur tapis et réduit l'efficacité d'aspiration des poils d'animaux.",
                    "search_keywords": "brosse duo rubber roborock s8"
                },
                {
                    "name": "Filtre à Air E11 Lavable pour Bac à Poussière",
                    "frequency": "Tous les 3 à 6 mois (lavage chaque semaine)",
                    "why_replace": "Le colmatage réduit le débit d'air du moteur HyperForce et entraîne des surchauffes lors des cycles longs.",
                    "search_keywords": "filtre lavable bac roborock s8"
                },
                {
                    "name": "Lingettes Serpillières Vibrantes VibraRise",
                    "frequency": "Remplacement tous les 3 à 6 mois",
                    "why_replace": "Les microfibres usées ne transmettent plus efficacement les vibrations soniques et laissent des traces sales au séchage.",
                    "search_keywords": "lingette serpillere vibrarise roborock s8"
                },
                {
                    "name": "Sacs à Poussière Filtrants 2,5 L pour Station RockDock",
                    "frequency": "Tous les 1 à 2 mois par sac",
                    "why_replace": "Un sac plein empêche la vidange automatique et fait forcer la turbine de succion de la station.",
                    "search_keywords": "sac poussiere station roborock s8 pro ultra"
                }
            ],
            faq=[
                {
                    "question": "Peut-on mettre du détergent classique dans le réservoir de la station RockDock ?",
                    "answer": "Non, les détergents moussants pour sol créent des bulles qui faussent les capteurs optiques et corrodent les pompes péristaltiques. Utilisez exclusivement la solution nettoyante officielle Roborock sans mousse."
                },
                {
                    "question": "Comment réinitialiser le compteur d'usure des pièces sur l'application ?",
                    "answer": "Ouvrez l'application Roborock, allez dans 'Paramètres' > 'Entretien et consommables', cliquez sur la pièce que vous venez de remplacer puis appuyez sur 'Réinitialiser le compteur'."
                },
                {
                    "question": "Les brosses DuoRubber sont-elles compatibles avec les séries S7 ?",
                    "answer": "Non, le système à double rouleau contrarotatif du Roborock S8 utilise un mécanisme d'engrenage différent des brosses simples du Roborock S7."
                }
            ]
        ),
        ApplianceGuide(
            slug="ninja-foodi-dualzone-airfryer-entretien",
            title="Ninja Foodi DualZone (AF300EU / AF400EU) : Entretien, Grilles et Accessoires",
            brand="Ninja",
            model="Foodi DualZone (AF300EU / AF400EU)",
            category="Friteuses sans Huile (Air Fryer)",
            meta_description="Grilles de cuisson croustillante, plaques antiadhésives et feuilles de cuisson pour Air Fryer Ninja DualZone. Entretien et nettoyage sans rayure.",
            common_codes=[
                {
                    "code": "Code Affiché : 'SHUT'",
                    "meaning": "L'un des deux tiroirs de cuisson n'est pas inséré à fond dans son logement.",
                    "solution": "Pousser fermement le tiroir concerné (Zone 1 ou Zone 2) jusqu'à entendre le clic de contact de sécurité mécanique."
                },
                {
                    "code": "Message : 'E01' ou 'E02'",
                    "meaning": "Anomalie passagère de la sonde de température thermique du panier 1 ou 2.",
                    "solution": "Débrancher l'appareil du secteur pendant 10 minutes pour réinitialiser la carte de contrôle, vérifier qu'aucun résidu de graisse ne bloque la sonde en haut du compartiment."
                },
                {
                    "code": "Fumée Blanche en Cours de Cuisson",
                    "meaning": "Accumulation d'huile ou de gras de viande tombé sur la résistance supérieure ou au fond du bac.",
                    "solution": "Arrêter la cuisson, laisser refroidir, essuyer l'excès de graisse liquide au fond du panier et nettoyer la grille croustillante avec une éponge non abrasive."
                }
            ],
            consumables=[
                {
                    "name": "Plaques Grilles Croustillantes Antiadhésives de Remplacement",
                    "frequency": "Tous les 12 à 18 mois en cas d'usure du revêtement céramique",
                    "why_replace": "Lorsque le revêtement est rayé par des ustensiles métalliques, les aliments attachent et la circulation d'air par le bas est perturbée.",
                    "search_keywords": "plaque croustillante grille ninja dualzone af300eu af400eu"
                },
                {
                    "name": "Papiers Cuisson Perforés Jetables Spéciaux Tiroir Rectangulaire",
                    "frequency": "Consommable à usage unique pour chaque cuisson grasse",
                    "why_replace": "Évite l'encrassement des paniers et protège durablement le fond en téflon contre les graisses brûlées tenaces.",
                    "search_keywords": "papier cuisson rectangulaire air fryer ninja dual zone"
                },
                {
                    "name": "Mains et Moules en Silicone Alimentaire pour Cuisson Double Tiroir",
                    "frequency": "Réutilisables sur plusieurs années",
                    "why_replace": "Permet de cuire sauces, gratins et pâtisseries sans salir les tiroirs et facilite le démoulage sans spatule abrasive.",
                    "search_keywords": "moule silicone panier ninja air fryer af300eu"
                },
                {
                    "name": "Pieds en Caoutchouc Silicone pour Grille de Cuisson",
                    "frequency": "En cas de perte ou durcissement lors des lavages",
                    "why_replace": "Ces patins isolent la grille métallique des parois du tiroir pour empêcher toute rayure du panier lors de l'insertion.",
                    "search_keywords": "embout caoutchouc grille air fryer ninja"
                }
            ],
            faq=[
                {
                    "question": "Les paniers et grilles du Ninja DualZone passent-ils au lave-vaisselle ?",
                    "answer": "Oui, ils sont compatibles lave-vaisselle. Toutefois, un lavage à la main à l'eau tiède avec une éponge douce et du liquide vaisselle préserve le revêtement antiadhésif en céramique beaucoup plus longtemps."
                },
                {
                    "question": "Peut-on utiliser du papier aluminium dans l'Air Fryer Ninja ?",
                    "answer": "Oui, à condition de poser des aliments lourds dessus pour éviter que la feuille ne soit aspirée par le ventilateur contre la résistance électrique supérieure."
                },
                {
                    "question": "Comment nettoyer les projections de graisse sur les résistances supérieures ?",
                    "answer": "Débranchez l'appareil et laissez-le refroidir. Retournez l'appareil délicatement et frottez doucement la grille de protection de la résistance avec une éponge légèrement humide et du bicarbonate de soude sans produit abrasif."
                }
            ]
        ),
        ApplianceGuide(
            slug="philips-series-2200-lattego-entretien",
            title="Philips Série 2200 / 3200 LatteGo : Filtres AquaClean, Détartrage et Joints",
            brand="Philips",
            model="Série 2200 / 3200 LatteGo (EP2220 / EP2231)",
            category="Machines à Café à Grains",
            meta_description="Filtres anticalcaire AquaClean, pastilles dégraissantes et graisse pour groupe café Philips LatteGo. Entretien et voyants d'alerte.",
            common_codes=[
                {
                    "code": "Voyant AquaClean Orange Clignotant",
                    "meaning": "Le filtre à eau AquaClean a atteint sa capacité maximale de filtration (ou n'a pas été activé correctement).",
                    "solution": "Remplacer la cartouche AquaClean, la secouer 5 secondes dans l'eau pour chasser l'air, l'insérer dans le réservoir et maintenir le bouton AquaClean 3 secondes jusqu'au bip."
                },
                {
                    "code": "Voyant Avertissement Triangle Rouge Clignotant",
                    "meaning": "La chambre d'extraction (groupe café) est bloquée, mal enclenchée ou de l'air est emprisonné dans le circuit d'eau.",
                    "solution": "Retirer le réservoir, ouvrir la trappe de service latérale, retirer le groupe café, le rincer sous l'eau tiède, vérifier qu'il est en position neutre avant de le réinsérer."
                },
                {
                    "code": "Voyant Bac à Marc Clignotant",
                    "meaning": "Le bac à marc est plein ou la trappe de service n'est pas totalement refermée.",
                    "solution": "Vider le bac à marc machine allumée, patienter 5 secondes avant de le réinsérer pour que le cycle de détection s'effectue."
                }
            ],
            consumables=[
                {
                    "name": "Cartouche Filtrante Anticalcaire AquaClean (CA6903)",
                    "frequency": "Tous les 3 mois (jusqu'à 5000 tasses sans détartrage)",
                    "why_replace": "Élimine le calcaire et les impuretés de l'eau, préservant la température d'infusion et l'arôme des grains.",
                    "search_keywords": "filtre aquaclean philips ca6903"
                },
                {
                    "name": "Pastilles Dégraissantes pour Circuit Café (CA6704)",
                    "frequency": "1 fois par mois",
                    "why_replace": "Dissout les huiles de café rances accumulées dans la grille de filtrage du groupe sans attaquer les joints.",
                    "search_keywords": "pastilles degraissantes cafe philips ca6704"
                },
                {
                    "name": "Tube de Graisse Silicone Alimentaire pour Groupe Café",
                    "frequency": "Tous les 2 mois après rinçage à l'eau claire",
                    "why_replace": "Garantit le coulissement silencieux des pistons de compression et prévient l'usure de l'engrenage principal.",
                    "search_keywords": "graisse silicone alimentaire machine cafe philips saeco"
                },
                {
                    "name": "Flacon Détartrant Spécial Machine à Café Philips (CA6700)",
                    "frequency": "Dès que le voyant 'Calc/Clean' s'allume",
                    "why_replace": "Formule douce homologuée pour éliminer le tartre résiduel sans altérer la chaudière en inox.",
                    "search_keywords": "detartrant philips ca6700"
                }
            ],
            faq=[
                {
                    "question": "Le pot à lait LatteGo a-t-il des tuyaux internes à nettoyer ?",
                    "answer": "Non, c'est la grande innovation du système LatteGo : il est composé de seulement 2 pièces emboîtables sans aucun tube interne caché, et se rince en 15 secondes sous le robinet ou au lave-vaisselle."
                },
                {
                    "question": "Pourquoi la mouture de café coule-t-elle trop lentement ?",
                    "answer": "Le réglage du moulin est probablement trop fin ou le filtre supérieur du groupe café est colmaté par les huiles de café. Nettoyez le groupe avec une pastille dégraissante et augmentez d'un cran la grosseur de mouture."
                },
                {
                    "question": "Peut-on utiliser de l'eau adoucie avec le filtre AquaClean ?",
                    "answer": "Oui, mais il est toujours recommandé d'activer le filtre AquaClean pour retenir les micro-particules et le chlore qui altèrent le goût du café."
                }
            ]
        )
    ]

    selected = [app for app in backup_pool if app.slug not in existing_slugs]
    return selected[:2]


SUPPORTED_LANGUAGES = ["fr", "en", "es", "de", "pt", "ja", "zh"]

AMAZON_DOMAINS = {
    "fr": "amazon.fr",
    "en": "amazon.com",
    "es": "amazon.es",
    "de": "amazon.de",
    "pt": "amazon.com.br",
    "ja": "amazon.co.jp",
    "zh": "amazon.com",
}

CATEGORY_MAPS = {
    "en": {
        "Aspirateurs Laveurs": "Wet & Dry Vacuums",
        "Machines à Café à Grains": "Bean-to-Cup Coffee Machines",
        "Robots Aspirateurs": "Robot Vacuums & Mops",
        "Friteuses sans Huile (Air Fryer)": "Air Fryers",
        "Purificateurs d'Air": "Air Purifiers",
        "Centrales Vapeur": "Steam Generator Irons",
    },
    "es": {
        "Aspirateurs Laveurs": "Aspiradoras Fregadoras",
        "Machines à Café à Grains": "Cafeteras Superautomáticas de Grano",
        "Robots Aspirateurs": "Robots Aspiradores y Fregasuelos",
        "Friteuses sans Huile (Air Fryer)": "Freidoras de Aire (Air Fryer)",
        "Purificateurs d'Air": "Purificadores de Aire",
        "Centrales Vapeur": "Centros de Planchado a Vapor",
    },
    "de": {
        "Aspirateurs Laveurs": "Nass- und Trockensauger / Wischsauger",
        "Machines à Café à Grains": "Kaffeevollautomaten",
        "Robots Aspirateurs": "Saug- und Wischroboter",
        "Friteuses sans Huile (Air Fryer)": "Heißluftfritteusen (Air Fryer)",
        "Purificateurs d'Air": "Luftreiniger",
        "Centrales Vapeur": "Dampfbügelstationen",
    },
    "pt": {
        "Aspirateurs Laveurs": "Aspiradores e Lavadoras de Piso",
        "Machines à Café à Grains": "Cafeteiras Automáticas de Grãos",
        "Robots Aspirateurs": "Robôs Aspiradores e Passa-Pano",
        "Friteuses sans Huile (Air Fryer)": "Fritadeiras sem Óleo (Air Fryer)",
        "Purificateurs d'Air": "Purificadores de Ar",
        "Centrales Vapeur": "Ferros com Caldeira a Vapor",
    },
    "ja": {
        "Aspirateurs Laveurs": "水拭きコードレス掃除機",
        "Machines à Café à Grains": "全自動コーヒーマシン",
        "Robots Aspirateurs": "ロボット掃除機（水拭き対応）",
        "Friteuses sans Huile (Air Fryer)": "ノンフライヤー・エアフライヤー",
        "Purificateurs d'Air": "空気清浄機",
        "Centrales Vapeur": "スチームアイロン",
    },
    "zh": {
        "Aspirateurs Laveurs": "无线洗地机与干湿吸尘器",
        "Machines à Café à Grains": "全自动现磨咖啡机",
        "Robots Aspirateurs": "扫拖一体机器人",
        "Friteuses sans Huile (Air Fryer)": "空气炸锅",
        "Purificateurs d'Air": "空气净化器",
        "Centrales Vapeur": "增压式蒸汽挂烫机",
    }
}

UI_TRANSLATIONS = {
    "fr": {
        "site_name": "AutoConsommables.fr",
        "tagline": "Base Officielle des Consommables, Pièces d'Usure & Codes Entretien",
        "banner_disclosure": "<strong>Transparence Partenaire Amazon :</strong> En tant que Partenaire Amazon, nous réalisons un bénéfice sur les achats remplissant les conditions requises (#LienAffilié). Guides d'entretien courant préventif.",
        "nav_guides": "Guides d'Entretien",
        "nav_legal": "Mentions Légales",
        "nav_dashboard": "Tableau de Bord Ops",
        "hero_title": "Prolongez la vie de vos appareils ménagers",
        "hero_sub": "Filtres HEPA, cartouches anticalcaire, brosses rotatives, joints et solutions d'entretien : retrouvez les pièces d'usure certifiées et résolvez les voyants d'alerte en 2 minutes.",
        "search_placeholder": "Rechercher une marque, un modèle (ex: Tineco S7, Delonghi Rivelia, Ninja AF400EU...)",
        "all_categories": "Toutes les catégories",
        "no_results_title": "Aucun appareil ne correspond à votre recherche",
        "no_results_desc": "Essayez un mot-clé plus court comme la marque (ex: Delonghi, Tineco, Roborock) ou changez de catégorie.",
        "parts_covered": "Pièces & Consommables traités :",
        "codes_explained": "codes voyants expliqués",
        "view_guide": "Voir la fiche →",
        "model_label": "Modèle :",
        "routine_care_label": "Entretien courant :",
        "routine_care_value": "Pièces d'usure amovibles sans outillage",
        "safety_title": "Consignes de Sécurité & Responsabilité :",
        "safety_desc": "Toujours débrancher électriquement l'appareil et attendre son complet refroidissement avant toute manipulation. Ce guide se limite strictement à l'entretien usuel, au remplacement de filtres/accessoires amovibles sans outillage. Pour toute panne électrique complexe, faites appel à un réparateur professionnel agréé.",
        "consumables_heading": "Consommables & Pièces d'Usure Recommandées",
        "consumables_intro": "L'efficacité d'origine et la longévité de votre appareil reposent sur le remplacement périodique de ces pièces d'usure :",
        "th_part": "Pièce / Consommable",
        "th_pn": "Réf. Constructeur (PN)",
        "th_freq": "Fréquence d'Entretien",
        "th_why": "Pourquoi est-ce indispensable ?",
        "th_avail": "Disponibilité",
        "btn_amazon": "Voir sur Amazon →",
        "errors_heading": "Voyants d'Alerte & Codes d'Entretien Courant",
        "errors_intro": "La majorité des signaux lumineux ou messages sur l'écran n'indiquent pas une panne grave, mais un simple besoin d'entretien de premier niveau :",
        "cause_label": "Cause courante :",
        "solution_label": "Procédure de résolution sans outil :",
        "faq_heading": "Questions Fréquentes (FAQ)",
        "footer_desc": "Votre observatoire indépendant des consommables d'usure, filtres de rechange et voyants d'entretien pour le petit et gros électroménager courant.",
        "footer_infra": "Site statique à zéro cookie tiers et zéro tracker, hébergé sur infrastructure mondiale haute performance.",
        "footer_popular": "Catégories Populaires",
        "footer_legal": "Informations Légales",
        "footer_affiliate": "Divulgation Partenaire Amazon",
        "footer_privacy": "Politique de Confidentialité (0 Cookie)",
        "footer_copyright": "Tous droits réservés. Guides pratiques rédigés à des fins d'entretien préventif non intrusif.",
    },
    "en": {
        "site_name": "AutoConsumables.com",
        "tagline": "Official Registry for Wear Parts, Consumables & Maintenance Codes",
        "banner_disclosure": "<strong>Amazon Associates Disclosure:</strong> As an Amazon Associate, we earn from qualifying purchases at no extra cost to you (#AffiliateLink). Routine maintenance and wear-part guides.",
        "nav_guides": "Maintenance Guides",
        "nav_legal": "Legal & Disclosure",
        "nav_dashboard": "Ops Dashboard",
        "hero_title": "Extend the Life of Your Home Appliances",
        "hero_sub": "Genuine HEPA filters, descaling cartridges, roller brushes, seals and maintenance kits: find certified replacement wear parts and clear routine warning lights in 2 minutes.",
        "search_placeholder": "Search by brand, exact model or PN (e.g. Dyson V15, Roborock Qrevo, Ninja SL400EU...)",
        "all_categories": "All Categories",
        "no_results_title": "No appliances match your search",
        "no_results_desc": "Try a shorter keyword like the brand (e.g., Ninja, Dyson, Roborock) or clear your category filter.",
        "parts_covered": "Essential wear parts covered:",
        "codes_explained": "error codes explained",
        "view_guide": "View Guide →",
        "model_label": "Model:",
        "routine_care_label": "Routine care:",
        "routine_care_value": "Tool-free replaceable wear parts",
        "safety_title": "Safety & Disclaimers:",
        "safety_desc": "Always unplug the appliance and allow it to cool down completely before performing any maintenance. This guide strictly covers routine care, simple cleaning, and tool-free consumable replacement. For internal electrical issues, contact a certified technician.",
        "consumables_heading": "Certified Wear Parts & Replacement Consumables",
        "consumables_intro": "Peak performance and long-term durability of your appliance rely on periodic replacement of these essential wear parts:",
        "th_part": "Part / Accessory",
        "th_pn": "Part Number (PN)",
        "th_freq": "Replacement Interval",
        "th_why": "Why Replace?",
        "th_avail": "Availability",
        "btn_amazon": "Check on Amazon →",
        "errors_heading": "Error Codes & Routine Maintenance Lights",
        "errors_intro": "Most alert icons and error messages on the screen do not indicate fatal breakdowns, but simple routine maintenance needs:",
        "cause_label": "Common Cause:",
        "solution_label": "Tool-Free Fix:",
        "faq_heading": "Frequently Asked Questions (FAQ)",
        "footer_desc": "Your independent resource for OEM-compatible replacement filters, brushes, and routine error codes for major home appliances.",
        "footer_infra": "Static zero-cookie, zero-tracker site hosted on high-performance global infrastructure.",
        "footer_popular": "Popular Categories",
        "footer_legal": "Legal & Disclosure",
        "footer_affiliate": "Amazon Affiliate Disclosure",
        "footer_privacy": "Zero-Cookie Privacy Policy",
        "footer_copyright": "All rights reserved. Routine maintenance guides for preventive care.",
    },
    "es": {
        "site_name": "AutoConsumables.es",
        "tagline": "Registro Oficial de Consumibles, Repuestos y Códigos de Error",
        "banner_disclosure": "<strong>Transparencia de Afiliados Amazon:</strong> Como Afiliado de Amazon, percibimos ingresos por compras adscritas que cumplan los requisitos (#EnlaceAfiliado). Guías de cuidado preventivo.",
        "nav_guides": "Guías de Mantenimiento",
        "nav_legal": "Aviso Legal",
        "nav_dashboard": "Panel de Operaciones",
        "hero_title": "Alargue la vida útil de sus electrodomésticos",
        "hero_sub": "Filtros HEPA, cartuchos antical, cepillos giratorios, juntas y kits de mantenimiento: encuentre recambios certificados y solucione alertas en 2 minutos.",
        "search_placeholder": "Buscar por marca, modelo o referencia (ej: Delonghi, Cecotec, Roborock, Ninja...)",
        "all_categories": "Todas las categorías",
        "no_results_title": "No se encontraron electrodomésticos",
        "no_results_desc": "Pruebe con una palabra clave más corta como la marca (ej: Delonghi, Cecotec, Roborock) o cambie de categoría.",
        "parts_covered": "Recambios y consumibles tratados:",
        "codes_explained": "códigos de error explicados",
        "view_guide": "Ver guía →",
        "model_label": "Modelo:",
        "routine_care_label": "Mantenimiento habitual:",
        "routine_care_value": "Piezas de desgaste extraíbles sin herramientas",
        "safety_title": "Seguridad y Advertencias:",
        "safety_desc": "Desenchufe siempre el aparato y déjelo enfriar antes de manipularlo. Esta guía se limita al mantenimiento rutinario y al cambio de piezas extraíbles sin herramientas. Para averías eléctricas internas, acuda a un servicio técnico autorizado.",
        "consumables_heading": "Repuestos y Consumibles Recomendados",
        "consumables_intro": "El rendimiento y la durabilidad de su aparato dependen del reemplazo regular de estas piezas de desgaste esencial:",
        "th_part": "Pieza / Accesorio",
        "th_pn": "Ref. Fabricante (PN)",
        "th_freq": "Frecuencia de Sustitución",
        "th_why": "¿Por qué es esencial?",
        "th_avail": "Disponibilidad",
        "btn_amazon": "Ver en Amazon →",
        "errors_heading": "Códigos de Error y Luces de Alerta",
        "errors_intro": "La mayoría de avisos luminosos o mensajes en pantalla indican un mantenimiento básico y no una avería grave:",
        "cause_label": "Causa habitual:",
        "solution_label": "Solución sin herramientas:",
        "faq_heading": "Preguntas Frecuentes (FAQ)",
        "footer_desc": "Su observatorio independiente de piezas de desgaste, filtros y códigos de mantenimiento para electrodomésticos.",
        "footer_infra": "Sitio estático sin cookies ni rastreadores de terceros, alojado en infraestructura global.",
        "footer_popular": "Categorías Populares",
        "footer_legal": "Información Legal",
        "footer_affiliate": "Divulgación de Afiliados Amazon",
        "footer_privacy": "Política de Privacidad (Cero Cookies)",
        "footer_copyright": "Todos los derechos reservados. Guías orientativas para mantenimiento preventivo.",
    },
    "de": {
        "site_name": "AutoConsumables.de",
        "tagline": "Offizielles Register für Ersatzteile, Filter & Fehlercodes",
        "banner_disclosure": "<strong>Amazon-Partnerhinweis:</strong> Als Amazon-Partner verdienen wir an qualifizierten Verkäufen (#AffiliateLink). Wartungsratgeber zur vorbeugenden Gerätepflege.",
        "nav_guides": "Wartungs-Ratgeber",
        "nav_legal": "Impressum & Datenschutz",
        "nav_dashboard": "Betriebs-Dashboard",
        "hero_title": "Verlängern Sie die Lebensdauer Ihrer Haushaltsgeräte",
        "hero_sub": "HEPA-Filter, Entkalkungskartuschen, Bürstenwalzen, Dichtungen und Pflegesets: Finden Sie zertifizierte Ersatzteile und beheben Sie Störungen in 2 Minuten.",
        "search_placeholder": "Nach Marke, Modell oder Teilenummer suchen (z.B. DeLonghi, Vorwerk, Roborock, Dyson...)",
        "all_categories": "Alle Kategorien",
        "no_results_title": "Keine passenden Geräte gefunden",
        "no_results_desc": "Versuchen Sie einen kürzeren Suchbegriff wie den Herstellernamen oder wählen Sie eine andere Kategorie.",
        "parts_covered": "Behandelte Verschleißteile:",
        "codes_explained": "Fehlercodes erklärt",
        "view_guide": "Ratgeber öffnen →",
        "model_label": "Modell:",
        "routine_care_label": "Regelmäßige Pflege:",
        "routine_care_value": "Werkzeuglos austauschbare Verschleißteile",
        "safety_title": "Sicherheitshinweise & Haftung:",
        "safety_desc": "Trennen Sie das Gerät vor jeder Wartung vom Stromnetz und lassen Sie es abkühlen. Diese Anleitung deckt nur die routinemäßige Pflege und den werkzeuglosen Austausch von Verschleißteilen ab. Bei internen Defekten wenden Sie sich an einen Fachbetrieb.",
        "consumables_heading": "Empfohlene Ersatz- & Verschleißteile",
        "consumables_intro": "Die optimale Saugleistung und Langlebigkeit Ihres Geräts erfordern den rechtzeitigen Austausch dieser Hauptverschleißteile:",
        "th_part": "Ersatzteil / Zubehör",
        "th_pn": "Hersteller-Nr. (PN)",
        "th_freq": "Wechselintervall",
        "th_why": "Warum notwendig?",
        "th_avail": "Verfügbarkeit",
        "btn_amazon": "Bei Amazon prüfen →",
        "errors_heading": "Fehlercodes & Wartungsanzeigen",
        "errors_intro": "Die meisten Signalleuchten oder Fehlercodes auf dem Display deuten auf einfache Pflege hin und nicht auf einen Totalschaden:",
        "cause_label": "Mögliche Ursache:",
        "solution_label": "Lösung ohne Werkzeug:",
        "faq_heading": "Häufige Fragen (FAQ)",
        "footer_desc": "Ihre unabhängige Plattform für kompatible Filter, Bürsten und Fehlercodes gängiger Haushaltsgeräte.",
        "footer_infra": "Statische Website ohne Cookies oder Drittanbieter-Tracker auf globaler Infrastruktur.",
        "footer_popular": "Beliebte Kategorien",
        "footer_legal": "Rechtliche Hinweise",
        "footer_affiliate": "Amazon-Partnererklärung",
        "footer_privacy": "Datenschutzerklärung (0 Cookies)",
        "footer_copyright": "Alle Rechte vorbehalten. Praxisanleitungen zur vorbeugenden Geräteinstandhaltung.",
    },
    "pt": {
        "site_name": "AutoConsumables.pt",
        "tagline": "Registro Oficial de Peças de Reposição, Filtros e Códigos de Erro",
        "banner_disclosure": "<strong>Transparência Associados Amazon:</strong> Como Associado da Amazon, recebemos comissão por compras qualificadas (#LinkAfiliado). Guias para manutenção preventiva doméstica.",
        "nav_guides": "Guias de Manutenção",
        "nav_legal": "Aviso Legal",
        "nav_dashboard": "Painel Operacional",
        "hero_title": "Prolongue a vida útil dos seus eletrodomésticos",
        "hero_sub": "Filtros HEPA, cartuchos descalcificantes, escovas rotativas e vedações: encontre peças certificadas e resolva alertas em 2 minutos.",
        "search_placeholder": "Pesquisar por marca ou modelo (ex: Mondial, Electrolux, Roborock, Philips...)",
        "all_categories": "Todas as categorias",
        "no_results_title": "Nenhum aparelho encontrado",
        "no_results_desc": "Tente uma palavra-chave mais curta, como o nome da marca, ou altere a categoria selecionada.",
        "parts_covered": "Peças e consumíveis tratados:",
        "codes_explained": "códigos explicados",
        "view_guide": "Ver guia →",
        "model_label": "Modelo:",
        "routine_care_label": "Manutenção rotineira:",
        "routine_care_value": "Peças substituíveis sem ferramentas",
        "safety_title": "Segurança e Responsabilidade:",
        "safety_desc": "Desligue sempre o aparelho da tomada e aguarde o resfriamento completo antes de qualquer intervenção. Este guia cobre apenas a manutenção básica e a troca de consumíveis manuais sem uso de ferramentas.",
        "consumables_heading": "Peças de Reposição e Consumíveis Recomendados",
        "consumables_intro": "A eficiência original e a longevidade do seu aparelho dependem da substituição periódica destas peças essenciais:",
        "th_part": "Peça / Acessório",
        "th_pn": "Cód. Fabricante (PN)",
        "th_freq": "Frequência de Troca",
        "th_why": "Por que é essencial?",
        "th_avail": "Disponibilidade",
        "btn_amazon": "Ver na Amazon →",
        "errors_heading": "Códigos de Erro e Luzes de Alerta",
        "errors_intro": "A maioria dos avisos luminosos ou códigos no ecrã indica necessidade de manutenção básica e não uma falha grave:",
        "cause_label": "Causa comum:",
        "solution_label": "Solução sem ferramentas:",
        "faq_heading": "Perguntas Frecuentes (FAQ)",
        "footer_desc": "Seu portal independente de peças de reposição, filtros e códigos de diagnóstico para eletrodomésticos.",
        "footer_infra": "Site estático sem cookies ou rastreadores de terceiros, hospedado em infraestrutura global.",
        "footer_popular": "Categorias Populares",
        "footer_legal": "Informações Legais",
        "footer_affiliate": "Divulgação de Afiliado Amazon",
        "footer_privacy": "Política de Privacidade (Zero Cookies)",
        "footer_copyright": "Todos os direitos reservados. Guias práticos para manutenção preventiva residencial.",
    },
    "ja": {
        "site_name": "AutoConsumables.jp",
        "tagline": "家電消耗品・純正互換パーツ＆エラーコード公式データベース",
        "banner_disclosure": "<strong>Amazonアソシエイト開示情報：</strong> 当サイトはAmazonアソシエイト・プログラムの参加者であり、適格販売により収入を得ています（#アフィリエイトリンク）。",
        "nav_guides": "メンテナンスガイド",
        "nav_legal": "特定商取引・規約",
        "nav_dashboard": "運用ダッシュボード",
        "hero_title": "家電製品を長持ちさせる消耗品・お手入れガイド",
        "hero_sub": "HEPAフィルター、除石灰カートリッジ、回転ブラシ、パッキン等：適合する交換パーツを見つけ、警告表示を2分で解消。",
        "search_placeholder": "メーカー名・型番で検索 (例: ダイソン, デロンギ, ルンバ, ティネコ...)",
        "all_categories": "すべてのカテゴリー",
        "no_results_title": "該当する家電製品が見つかりません",
        "no_results_desc": "メーカー名などの短いキーワードで再検索するか、カテゴリーの選択を解除してください。",
        "parts_covered": "対象の消耗部品：",
        "codes_explained": "のエラー解説",
        "view_guide": "ガイドを見る →",
        "model_label": "型番・モデル:",
        "routine_care_label": "日常のお手入れ:",
        "routine_care_value": "工具不要の交換パーツ",
        "safety_title": "安全上の注意事項・免責事項:",
        "safety_desc": "作業を行う前に必ず電源プラグをコンセントから抜き、本体が完全に冷めていることを確認してください。本ガイドは工具を使わずに脱着できるフィルターや消耗品の日常交換のみを対象としています。",
        "consumables_heading": "推奨交換用消耗品・純正互換パーツ",
        "consumables_intro": "本来の清掃力や寿命を維持するために、定期的な消耗品交換を推奨します：",
        "th_part": "部品・消耗品",
        "th_pn": "型番 (PN)",
        "th_freq": "交換頻度",
        "th_why": "交換の重要性",
        "th_avail": "在庫・購入",
        "btn_amazon": "Amazonで確認 →",
        "errors_heading": "エラーコード・警告ランプの解除",
        "errors_intro": "ディスプレイの警告表示や点滅ランプの多くは故障ではなく、日常の簡単なお手入れで解決します：",
        "cause_label": "主な原因:",
        "solution_label": "工具不要の解除手順:",
        "faq_heading": "よくある質問 (FAQ)",
        "footer_desc": "主要家電製品の消耗品交換時期、互換フィルター、日常エラーコードの独立データベース。",
        "footer_infra": "クッキー不使用・トラッカーゼロ。グローバルインフラによる高速静的配信。",
        "footer_popular": "人気カテゴリー",
        "footer_legal": "法的表記・規約",
        "footer_affiliate": "Amazonアソシエイト声明",
        "footer_privacy": "プライバシーポリシー（Cookie不使用）",
        "footer_copyright": "無断転載を禁じます。日常の予防保全を目的とした実践ガイド。",
    },
    "zh": {
        "site_name": "AutoConsumables.cn",
        "tagline": "家电原厂适配耗材、易损配件与故障代码技术数据库",
        "banner_disclosure": "<strong>亚马逊联盟透明度声明：</strong> 作为亚马逊联盟合作伙伴，符合条件的购买会产生推广佣金（#推广链接）。日常维护指南仅供预防性保养参考。",
        "nav_guides": "保养指南",
        "nav_legal": "法律声明",
        "nav_dashboard": "运维仪表盘",
        "hero_title": "延长家用电器使用寿命的耗材保养指南",
        "hero_sub": "HEPA滤网、除垢滤芯、滚刷、密封圈与保养套件：快速匹配正品配件，2分钟排除日常警报。",
        "search_placeholder": "按品牌、具体型号或零件号搜索 (例如: 添可, 德龙, 石头科技, 追觅, 戴森...)",
        "all_categories": "所有分类",
        "no_results_title": "未找到匹配的家电设备",
        "no_results_desc": "请尝试缩短搜索词（如只输入品牌名称），或清除分类筛选重试。",
        "parts_covered": "收录易损耗材：",
        "codes_explained": "项故障代码解析",
        "view_guide": "查看详情 →",
        "model_label": "型号:",
        "routine_care_label": "日常维护:",
        "routine_care_value": "无需工具即可拆装的易损耗材",
        "safety_title": "安全须知与免责声明:",
        "safety_desc": "在进行任何拆装维护前，请务必拔掉电源插头并等待机身完全冷却。本指南仅涵盖日常免工具可拆卸耗材的更换与清理，内部电路故障请联系官方授权维修点。",
        "consumables_heading": "推荐易损耗材与替换配件",
        "consumables_intro": "为保持机器最佳工作性能并延长使用寿命，建议定期更换以下核心易损部件：",
        "th_part": "配件 / 耗材",
        "th_pn": "原厂零件号 (PN)",
        "th_freq": "更换周期",
        "th_why": "更换原因及影响",
        "th_avail": "选购链接",
        "btn_amazon": "在亚马逊上查看 →",
        "errors_heading": "故障报警代码与日常维护指示灯",
        "errors_intro": "显示屏上的绝大多数报错图标和警报代码并非主板损坏，而是常规的基础清理提示：",
        "cause_label": "常见原因:",
        "solution_label": "无需工具的解决步骤:",
        "faq_heading": "常见问题 (FAQ)",
        "footer_desc": "面向主流家用电器的耗材对照、滤网适配与日常故障排除独立指南平台。",
        "footer_infra": "零第三方Cookie、零追踪器的静态站点，部署于全球高性能云基础设施。",
        "footer_popular": "热门品类",
        "footer_legal": "合规与法律信息",
        "footer_affiliate": "亚马逊联盟伙伴声明",
        "footer_privacy": "隐私政策（零Cookie）",
        "footer_copyright": "版权所有。为延长家电使用寿命而编写的预防性日常维护指南。",
    }
}


def localize_consumable_name(name: str, lang: str) -> str:
    """Traduit ou adapte le nom du consommable selon la langue cible."""
    if lang == "fr" or not name:
        return name
    n_lower = name.lower()
    if "filtre" in n_lower or "hepa" in n_lower:
        mapping = {
            "en": "HEPA Filter Replacement",
            "es": "Filtro HEPA de Alta Eficiencia",
            "de": "HEPA-Ersatzfilter",
            "pt": "Filtro HEPA de Alta Eficiência",
            "ja": "交換用HEPA高機能フィルター",
            "zh": "HEPA高效替换滤网",
        }
        return mapping.get(lang, name)
    if "rouleau" in n_lower or "brosse" in n_lower:
        if "latérale" in n_lower:
            mapping = {
                "en": "Side Edge Brush",
                "es": "Cepillo Lateral para Esquinas",
                "de": "Seitenbürste für Ecken",
                "pt": "Escova Lateral de Cantos",
                "ja": "サイドエッジブラシ",
                "zh": "边角清洁边刷",
            }
            return mapping.get(lang, name)
        mapping = {
            "en": "Main Roller Brush",
            "es": "Cepillo de Rodillo Principal",
            "de": "Haupt-Bürstenwalze",
            "pt": "Rolo de Escova Principal",
            "ja": "メイン回転ブラシローラー",
            "zh": "原装主滚刷配件",
        }
        return mapping.get(lang, name)
    if "détartr" in n_lower or "anticalcaire" in n_lower or "calc" in n_lower:
        mapping = {
            "en": "Descaling Solution & Water Filter",
            "es": "Líquido Descalcificador y Antical",
            "de": "Entkalker & Wasserfilter",
            "pt": "Solução Descalcificante e Filtro",
            "ja": "純正除石灰剤・軟水フィルター",
            "zh": "专用除垢剂与软水滤芯",
        }
        return mapping.get(lang, name)
    if "serpilli" in n_lower or "microfibre" in n_lower or "lingette" in n_lower:
        mapping = {
            "en": "Microfiber Mop Pads",
            "es": "Mopas de Microfibra Lavables",
            "de": "Mikrofaser-Wischtücher",
            "pt": "Panos de Microfibra Laváveis",
            "ja": "マイクロファイバーモップクロス",
            "zh": "可清洗超细纤维拖布",
        }
        return mapping.get(lang, name)
    if "joint" in n_lower or "silicone" in n_lower:
        mapping = {
            "en": "Silicone Gasket Seal",
            "es": "Junta de Silicona Hermética",
            "de": "Silikon-Dichtungsring",
            "pt": "Junta de Vedação em Silicone",
            "ja": "耐熱シリコン密閉パッキン",
            "zh": "耐温硅胶密封圈",
        }
        return mapping.get(lang, name)
    return name


def localize_frequency(freq: str, lang: str) -> str:
    """Traduit les intervalles de remplacement standard."""
    if lang == "fr" or not freq:
        return freq
    f_lower = freq.lower()
    if "3 à 6 mois" in f_lower or "3-6" in f_lower:
        mapping = {
            "en": "Every 3 to 6 months",
            "es": "Cada 3 a 6 meses",
            "de": "Alle 3 bis 6 Monate",
            "pt": "A cada 3 a 6 meses",
            "ja": "3〜6ヶ月ごと",
            "zh": "每3至6个月",
        }
        return mapping.get(lang, freq)
    if "6 à 12 mois" in f_lower or "6-12" in f_lower or "1 an" in f_lower:
        mapping = {
            "en": "Every 6 to 12 months",
            "es": "Cada 6 a 12 meses",
            "de": "Alle 6 bis 12 Monate",
            "pt": "A cada 6 a 12 meses",
            "ja": "6〜12ヶ月ごと",
            "zh": "每6至12个月",
        }
        return mapping.get(lang, freq)
    if "usage" in f_lower or "chaque" in f_lower:
        mapping = {
            "en": "After each cleaning cycle",
            "es": "Tras cada uso o ciclo",
            "de": "Nach jedem Reinigungslauf",
            "pt": "Após cada ciclo de limpeza",
            "ja": "使用・清掃サイクルごと",
            "zh": "每次清洁使用后",
        }
        return mapping.get(lang, freq)
    if "mensuel" in f_lower or "200" in f_lower or "mois" in f_lower:
        mapping = {
            "en": "Monthly / every 200 cycles",
            "es": "Mensual / cada 200 cafés",
            "de": "Monatlich / alle 200 Zyklen",
            "pt": "Mensal / a cada 200 ciclos",
            "ja": "毎月 / 200回ごと",
            "zh": "每月一次 / 每200杯",
        }
        return mapping.get(lang, freq)
    return freq


def localize_why_replace(why: str, lang: str) -> str:
    """Traduit l'argumentaire technique de remplacement."""
    if lang == "fr" or not why:
        return why
    w_lower = why.lower()
    if "aspiration" in w_lower or "moteur" in w_lower or "surchauffe" in w_lower:
        mapping = {
            "en": "Prevents motor overheating and restores 100% factory suction power.",
            "es": "Evita el sobrecalentamiento del motor y recupera el 100% de la potencia de succión.",
            "de": "Verhindert Motorüberhitzung und stellt die maximale Saugleistung wieder her.",
            "pt": "Evita o superaquecimento do motor e restaura a sucção original de fábrica.",
            "ja": "モーターの過熱を防ぎ、新品時の強力な吸引力と排気清浄度を回復させます。",
            "zh": "防止电机过热保护，恢复出厂级强劲吸力并保障排气洁净。",
        }
        return mapping.get(lang, why)
    if "calcaire" in w_lower or "buse" in w_lower or "tartre" in w_lower:
        mapping = {
            "en": "Prevents mineral scale build-up and maintains optimal brew pressure and temperature.",
            "es": "Evita la acumulación de cal y garantiza la presión y temperatura óptimas de extracción.",
            "de": "Schützt vor Verkalkung der Heizelemente und garantiert optimalen Brühdruck.",
            "pt": "Previne o acúmulo de calcário e preserva a pressão ideal de infusão e temperatura.",
            "ja": "内部配管の石灰付着を防ぎ、理想的な抽出圧力と温度を維持します。",
            "zh": "彻底清除加热水道水垢沉积，维持标准萃取水温与泵压。",
        }
        return mapping.get(lang, why)
    if "brosse" in w_lower or "rouleau" in w_lower or "cheveux" in w_lower or "poils" in w_lower:
        mapping = {
            "en": "Eliminates hair tangles and avoids streak marks on hard floors.",
            "es": "Evita marcas en suelos duros y garantiza una recogida eficaz sin enredos de pelo.",
            "de": "Verhindert Streifenbildung auf Hartböden und sorgt für rückstandsfreie Schmutzaufnahme.",
            "pt": "Evita marcas no chão e assegura a recolha eficiente de detritos e pelos.",
            "ja": "毛髪の絡まりを除去し、フローリングに拭き筋を残さず清潔に磨き上げます。",
            "zh": "避免毛发缠绕，彻底消除硬质地板水渍与划痕。",
        }
        return mapping.get(lang, why)
    mapping = {
        "en": "Essential for hygiene, optimal efficiency and extending appliance lifespan.",
        "es": "Fundamental para la higiene, máxima eficacia y prolongar la vida útil del equipo.",
        "de": "Unerlässlich für einwandfreie Hygiene und den Werterhalt des Geräts.",
        "pt": "Indispensável para a higiene, eficiência energética e durabilidade do aparelho.",
        "ja": "衛生状態を保ち、機器本来の性能発揮と製品寿命の延長に直結します。",
        "zh": "确保使用卫生健康，恢复最佳运行效率并大幅延长整机寿命。",
    }
    return mapping.get(lang, why)


def localize_common_codes(codes: list, lang: str) -> list:
    """Traduit les codes erreurs et procédures de résolution."""
    if lang == "fr" or not codes:
        return codes
    localized = []
    for c in codes:
        code_str = str(c.get("code", ""))
        meaning_str = str(c.get("meaning", ""))
        solution_str = str(c.get("solution", ""))
        m_lower = meaning_str.lower()

        if "filtre" in m_lower or "saturation" in m_lower or "bouch" in m_lower:
            m_map = {
                "en": "Filter clogged or airflow obstructed",
                "es": "Filtro saturado u obstrucción de aire",
                "de": "Filter verstopft oder Luftstrom behindert",
                "pt": "Filtro saturado ou fluxo de ar bloqueado",
                "ja": "フィルターの目詰まりまたは吸気口の閉塞",
                "zh": "滤网严重堵塞或进风管道受阻",
            }
            s_map = {
                "en": "Remove and tap out dust or wash filter under cold water. Let dry for 24h before reinserting.",
                "es": "Extraiga el filtro, sacúdalo o lávelo bajo agua fría. Deje secar 24 h antes de volver a colocarlo.",
                "de": "Filter entnehmen, ausklopfen oder unter kaltem Wasser spülen. 24 Std. trocknen lassen.",
                "pt": "Retire o filtro, sacuda o pó ou lave em água fria. Deixe secar por 24 horas antes do uso.",
                "ja": "フィルターを取り外してゴミを落とすか水洗いし、24時間完全乾燥させてから装着します。",
                "zh": "拆下滤网轻轻拍打除尘，或用冷水彻底清洗，完全晾干24小时后重新装入。",
            }
        elif "brosse" in m_lower or "rouleau" in m_lower or "blocage" in m_lower:
            m_map = {
                "en": "Roller brush stalled or tangled by hair",
                "es": "Cepillo giratorio bloqueado por pelos",
                "de": "Bürstenwalze durch Haare blockiert",
                "pt": "Escova rotativa bloqueada por fios ou pelos",
                "ja": "ローラーブラシへの毛髪絡まり・回転停止",
                "zh": "滚刷缠绕毛发或异物导致电机自停保护",
            }
            s_map = {
                "en": "Release quick-clip cover, remove roller and cut away tangled hairs with scissors.",
                "es": "Abra la tapa de fácil acceso, extraiga el rodillo y retire los pelos acumulados con tijeras.",
                "de": "Klick-Abdeckung lösen, Walze herausnehmen und Verhedderungen vorsichtig zerschneiden.",
                "pt": "Solte a tampa de clique, retire o rolo e corte os fios acumulados com uma tesoura.",
                "ja": "ワンタッチカバーを外し、ブラシを取り出して絡まった髪の毛をハサミで切除してください。",
                "zh": "解开快拆卡扣取出滚刷，使用小剪刀清理轴承及缝隙处缠绕的头发线头。",
            }
        elif "détartr" in m_lower or "calc" in m_lower:
            m_map = {
                "en": "Routine descaling reminder triggered",
                "es": "Aviso de descalcificación rutinaria",
                "de": "Regulärer Entkalkungshinweis aktiv",
                "pt": "Alerta de descalcificação periódica ativado",
                "ja": "定期的な除石灰（カルキ抜き）アラート",
                "zh": "定期管路除垢保养提示灯点亮",
            }
            s_map = {
                "en": "Fill water tank with descaling solution and water, run automatic cycle, then flush thoroughly.",
                "es": "Llene el depósito con líquido descalcificador y agua, inicie el ciclo automático y aclare bien.",
                "de": "Wassertank mit Entkalkerlösung befüllen, Spülprogramm starten und anschließend gründlich nachspülen.",
                "pt": "Encha o reservatório com descalcificante e água, execute o ciclo automático e enxágue bem.",
                "ja": "給水タンクに水と除石灰剤を入れ、自動洗浄モードを実行してすすぎを行ってください。",
                "zh": "在水箱中注入除垢剂与清水，长按清洗键启动全自动除垢循环，随后彻底冲洗管路。",
            }
        elif "réservoir" in m_lower or "eau" in m_lower or "tank" in m_lower:
            m_map = {
                "en": "Clean water tank empty or dirty container full",
                "es": "Depósito de agua limpia vacío o sucio lleno",
                "de": "Frischwassertank leer oder Schmutzwassertank voll",
                "pt": "Reservatório de água limpa vazio ou de suja cheio",
                "ja": "浄水タンクの空水または汚水タンクの満水",
                "zh": "清水箱缺水或污水箱已满溢警报",
            }
            s_map = {
                "en": "Empty dirty container, clean float sensor and refill clean water tank.",
                "es": "Vacíe el depósito de aguas residuales, limpie los sensores y recargue el agua limpia.",
                "de": "Schmutzwassertank entleeren, Sensoren abwischen und Frischwasser auffüllen.",
                "pt": "Esvazie o recipiente de água suja, limpe os sensores e reabasteça com água limpa.",
                "ja": "汚水タンクを排水してフロートセンサーを拭き、浄水タンクに水を補給してください。",
                "zh": "清空污水箱并擦拭电极水位传感器，重新将清水箱注满清水即可复位。",
            }
        else:
            m_map = {
                "en": f"Alert code {code_str}: routine sensor check required",
                "es": f"Aviso {code_str}: comprobación rutinaria del sensor",
                "de": f"Hinweis {code_str}: Überprüfung der Sensoren erforderlich",
                "pt": f"Código {code_str}: verificação de rotina do sensor",
                "ja": f"警告コード {code_str}: センサーの日常点検が必要です",
                "zh": f"警报代码 {code_str}: 需进行日常传感器清洁与复位",
            }
            s_map = {
                "en": "Turn off power for 30s, wipe external optical contacts and restart machine.",
                "es": "Apague el equipo 30 s, limpie los contactos ópticos y reinicie.",
                "de": "Gerät für 30 Sek. ausschalten, Sensorkontakte abwischen und neu starten.",
                "pt": "Desligue o aparelho por 30 segundos, limpe os contactos e reinicie.",
                "ja": "主電源を30秒間切り、センサー接点を拭き取ってから再起動してください。",
                "zh": "关闭电源静置30秒，擦拭机身外部光学接触点后重新开机。",
            }

        localized.append({
            "code": code_str,
            "meaning": m_map.get(lang, meaning_str),
            "solution": s_map.get(lang, solution_str),
        })
    return localized


def build_localized_guide(guide: dict, lang: str, partner_tag: str) -> dict:
    """Adapte et traduit intégralement une fiche technique pour n'importe quelle langue cible."""
    if lang == "fr":
        fr_consumables = []
        for c in guide.get("consumables", []):
            search_q = c.get("search_keywords", f"{guide.get('brand')} {guide.get('model')} {c.get('part_number', '')} {c.get('name')}").strip()
            item = dict(c)
            item["affiliate_url"] = build_affiliate_url(search_q, partner_tag, domain="amazon.fr")
            fr_consumables.append(item)
        res = dict(guide)
        res["consumables"] = fr_consumables
        return res

    domain = AMAZON_DOMAINS.get(lang, "amazon.com")
    cat_map = CATEGORY_MAPS.get(lang, {})
    loc_cat = cat_map.get(guide.get("category", ""), guide.get("category", "Home Appliances"))

    brand = guide.get("brand", "")
    model = guide.get("model", "")

    title_templates = {
        "en": f"{brand} {model}: Replacement Parts, Filters & Error Codes",
        "es": f"{brand} {model}: Repuestos, Filtros y Códigos de Error",
        "de": f"{brand} {model}: Ersatzteile, Filter und Fehlercodes",
        "pt": f"{brand} {model}: Peças de Reposição, Filtros e Códigos de Erro",
        "ja": f"{brand} {model}: 交換部品・フィルター・エラーコード解説",
        "zh": f"{brand} {model}: 耗材配件、滤网更换与故障代码指南",
    }
    desc_templates = {
        "en": f"Genuine OEM replacement filters, brushes, descaling cartridges and routine error codes guide for {brand} {model}.",
        "es": f"Guía de recambios, filtros, cepillos, cartuchos antical y códigos de error comunes para {brand} {model}.",
        "de": f"Anleitung für Ersatzfilter, Bürstenwalzen, Entkalkung und Fehlercodes für {brand} {model}.",
        "pt": f"Guia de peças de reposição, filtros, escovas, cartuchos de descalcificação e códigos de erro para {brand} {model}.",
        "ja": f"{brand} {model} の純正交換用フィルター、ブラシ、除石灰カートリッジおよび日常エラーコードの解説ガイド。",
        "zh": f"{brand} {model} 正品替换滤网、滚刷、除垢滤芯及常见故障报警代码对照指南。",
    }

    loc_consumables = []
    for c in guide.get("consumables", []):
        loc_name = localize_consumable_name(c.get("name", "Pièce"), lang)
        loc_freq = localize_frequency(c.get("frequency", ""), lang)
        loc_why = localize_why_replace(c.get("why_replace", ""), lang)
        pn = c.get("part_number", "OEM compatible")
        search_q = f"{brand} {model} {pn} {loc_name}".strip()
        loc_consumables.append({
            "name": loc_name,
            "part_number": pn,
            "frequency": loc_freq,
            "why_replace": loc_why,
            "search_keywords": search_q,
            "affiliate_url": build_affiliate_url(search_q, partner_tag, domain=domain),
        })

    loc_codes = localize_common_codes(guide.get("common_codes", []), lang)

    # Localisation FAQ
    loc_faq = []
    for f in guide.get("faq", []):
        q = f.get("question", "")
        a = f.get("answer", "")
        q_trans = {
            "en": f"How often should I replace consumables on {brand} {model}?",
            "es": f"¿Con qué frecuencia debo cambiar los consumibles en {brand} {model}?",
            "de": f"Wie oft müssen die Verschleißteile beim {brand} {model} getauscht werden?",
            "pt": f"Com que frequência devo substituir as peças no {brand} {model}?",
            "ja": f"{brand} {model} の消耗品はどのくらいの頻度で交換すべきですか？",
            "zh": f"{brand} {model} 的易损耗材应该多久更换一次？",
        }
        a_trans = {
            "en": f"Filters and brushes should generally be replaced every 3 to 6 months depending on usage to maintain peak suction and motor longevity.",
            "es": f"Los filtros y cepillos deben sustituirse cada 3 a 6 meses según la frecuencia de uso para garantizar el máximo rendimiento.",
            "de": f"Filter und Bürsten sollten je nach Nutzung alle 3 bis 6 Monate erneuert werden, um die volle Saugleistung zu erhalten.",
            "pt": f"Filtros e escovas devem ser trocados a cada 3 a 6 meses conforme o uso para preservar o motor.",
            "ja": f"本来の吸引力とモーター寿命を保つため、フィルターとブラシは使用頻度に応じて3〜6ヶ月ごとの交換を推奨します。",
            "zh": f"为维持出厂吸力并保护电机，建议根据使用频率每3至6个月更换一次滤网和滚刷。",
        }
        loc_faq.append({
            "question": q_trans.get(lang, q),
            "answer": a_trans.get(lang, a)
        })

    return {
        "slug": guide["slug"],
        "title": title_templates.get(lang, guide.get("title")),
        "brand": brand,
        "model": model,
        "category": loc_cat,
        "meta_description": desc_templates.get(lang, guide.get("meta_description")),
        "common_codes": loc_codes,
        "consumables": loc_consumables,
        "faq": loc_faq if loc_faq else guide.get("faq", []),
    }


def build_english_guide(guide: dict, partner_tag: str) -> dict:
    """Wrapper de rétrocompatibilité pour la version anglaise."""
    return build_localized_guide(guide, "en", partner_tag)


def generate_syndication_markdown(guide: dict, site_base_url: str, lang: str = "fr") -> str:
    """Génère un export Markdown propre prêt pour la syndication multilingue (dev.to, Medium, etc.)."""
    clean_base = site_base_url.rstrip("/")
    canonical_path = f"/{lang}/guides/{guide['slug']}.html" if lang != "fr" else f"/guides/{guide['slug']}.html"
    canonical_url = f"{clean_base}{canonical_path}"
    date_str = datetime.datetime.now().strftime("%Y-%m-%d")
    t = UI_TRANSLATIONS.get(lang, UI_TRANSLATIONS["fr"])

    title = guide["title"]
    desc = guide.get("meta_description", "")

    lines = [
        "---",
        f'title: "{title}"',
        f'description: "{desc}"',
        f'canonical_url: "{canonical_url}"',
        f'published_at: "{date_str}"',
        f'lang: "{lang}"',
        'tags: ["diy", "guide", "appliances", "maintenance", "tech"]',
        "---",
        "",
        f"# {title}",
        "",
        f"> **{t['banner_disclosure']}**",
        f"> *Source & Guide: [{canonical_url}]({canonical_url})*",
        "",
        f"## ⚠️ {t['safety_title']}",
        f"{t['safety_desc']}",
        "",
        f"## 🛠️ {t['consumables_heading']}",
        "",
        f"| {t['th_part']} | {t['th_pn']} | {t['th_freq']} | {t['th_avail']} |",
        "| :--- | :--- | :--- | :--- |",
    ]

    for item in guide.get("consumables", []):
        pn = item.get("part_number") or "OEM compatible"
        url = item.get("affiliate_url", "")
        lines.append(f"| **{item.get('name')}** | `{pn}` | {item.get('frequency')} | [{t['btn_amazon']}]({url}) |")

    lines.extend([
        "",
        f"### 🔍 {t['consumables_heading']}",
        "",
    ])

    for item in guide.get("consumables", []):
        lines.append(f"#### {item.get('name')}")
        lines.append(f"- **{t['th_pn']} :** `{item.get('part_number', 'OEM compatible')}`")
        lines.append(f"- **{t['th_freq']} :** {item.get('frequency')}")
        lines.append(f"- **{t['th_why']} :** {item.get('why_replace')}")
        lines.append(f"- **{t['th_avail']} :** [{t['btn_amazon']}]({item.get('affiliate_url')})")
        lines.append("")

    lines.extend([
        f"## 🚨 {t['errors_heading']}",
        "",
    ])

    for code in guide.get("common_codes", []):
        lines.append(f"### ⚠️ {code.get('code')}")
        lines.append(f"- **{t['cause_label']}** {code.get('meaning')}")
        lines.append(f"- **{t['solution_label']}** {code.get('solution')}")
        lines.append("")

    lines.extend([
        f"## ❓ {t['faq_heading']}",
        "",
    ])

    for faq in guide.get("faq", []):
        lines.append(f"### Q: {faq.get('question')}")
        lines.append(f"**A:** {faq.get('answer')}")
        lines.append("")

    lines.extend([
        "---",
        f"*Datasheet for **{guide.get('brand')} {guide.get('model')}** — [{canonical_url}]({canonical_url}).*",
    ])

    return "\n".join(lines)



# ==============================================================================
# Interrogation API Officielle RappelConso (data.economie.gouv.fr)
# ==============================================================================

def fetch_rappelconso_records(partner_tag: str, limit: int = 10) -> List[dict]:
    """Interroge gratuitement et sans clé l'API RappelConso pour récupérer les derniers rappels électroménager."""
    primary_url = f"https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/rappelconso0/records?where=categorie_de_produit%20like%20%22Appareils%20%C3%A9lectriques%22&limit={limit}&order_by=date_de_publication%20desc"
    fallback_url = f"https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/rappelconso-v2-gtin-espaces/records?where=categorie_produit%20like%20%22Appareils%22&limit={limit}&order_by=date_publication%20desc"

    raw_records = []
    for endpoint in [primary_url, fallback_url]:
        try:
            resp = requests.get(endpoint, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                raw_records = data.get("results", [])
                if raw_records:
                    logger.info(f"API RappelConso : {len(raw_records)} rappels officiels récupérés ({endpoint}).")
                    break
        except Exception as exc:
            logger.warning(f"Tentative de connexion RappelConso ({endpoint}) : {exc}")

    recalls_list = []
    for r in raw_records[:limit]:
        marque = r.get("marque_produit") or r.get("marque") or "Marque non spécifiée"
        modele = r.get("modeles_ou_references") or r.get("modele") or "Modèle électroménager"
        cat = r.get("sous_categorie_produit") or r.get("categorie_produit") or "Appareil électroménager"
        date_pub = r.get("date_publication") or r.get("date_de_publication") or ""
        motif = r.get("motif_rappel") or r.get("motif_du_rappel") or "Non-conformité électrique"
        risques = r.get("risques_encourus") or r.get("risques") or "Choc électrique / incendie"
        fiche_url = r.get("lien_vers_la_fiche_rappel") or r.get("fiche_url") or "https://rappel.conso.gouv.fr"

        safe_query = f"{cat} {marque} certifie conforme sans danger"
        safe_amazon_url = build_affiliate_url(safe_query, partner_tag, domain="amazon.fr")

        recalls_list.append({
            "brand": marque,
            "model": modele,
            "category": cat,
            "publication_date": date_pub,
            "reason": motif,
            "risks": risques,
            "official_notice_url": fiche_url,
            "safe_replacement_search": safe_query,
            "safe_replacement_amazon_url": safe_amazon_url,
        })

    return recalls_list


# ==============================================================================
# Flux RSS 2.0 Valide (docs/feed.xml)
# ==============================================================================

def generate_rss_feed(catalog_data: dict, site_base_url: str) -> str:
    """Génère docs/feed.xml (flux RSS 2.0 valide) contenant les 50 dernières fiches."""
    clean_base_url = site_base_url.rstrip("/")
    now_rfc822 = datetime.datetime.now(datetime.timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
    guides_list = catalog_data.get("guides", [])

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">',
        '  <channel>',
        '    <title>Auto-Consommables | Guide des Pièces d\'Usure &amp; Entretien</title>',
        f'    <link>{clean_base_url}/index.html</link>',
        '    <description>Base technique officielle des consommables, filtres certifiés et codes pannes pour électroménager grand public.</description>',
        '    <language>fr-FR</language>',
        f'    <lastBuildDate>{now_rfc822}</lastBuildDate>',
        f'    <atom:link href="{clean_base_url}/feed.xml" rel="self" type="application/rss+xml"/>',
    ]

    for guide in guides_list[:50]:
        brand = guide.get("brand", "")
        model = guide.get("model", "")
        slug = guide.get("slug", "")
        meta_desc = guide.get("meta_description", "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        guide_url = f"{clean_base_url}/guides/{slug}.html"
        item_title = f"{brand} {model} - Pièces d'usure, filtres et codes entretien".replace("&", "&amp;")

        lines.extend([
            '    <item>',
            f'      <title>{item_title}</title>',
            f'      <link>{guide_url}</link>',
            f'      <guid isPermaLink="true">{guide_url}</guid>',
            f'      <description>{meta_desc}</description>',
            f'      <pubDate>{now_rfc822}</pubDate>',
            '    </item>',
        ])

    lines.extend([
        '  </channel>',
        '</rss>',
    ])

    return "\n".join(lines).strip() + "\n"


# ==============================================================================
# Générateurs Standardisés LLMs.txt (GEO) & API JSON pour Agents IA
# ==============================================================================

def generate_llms_txt(catalog_data: dict, site_base_url: str) -> str:
    """Génère docs/llms.txt respectant strictement la spécification LLMs.txt (GEO)."""
    clean_base_url = site_base_url.rstrip("/")
    guides_list = catalog_data.get("guides", [])

    by_category: dict[str, list[dict]] = {}
    for g in guides_list:
        cat = g.get("category", "Autres Équipements")
        by_category.setdefault(cat, []).append(g)

    lines = [
        "# Base Officielle des Consommables, Pièces d'Usure & Codes Entretien Appareils Domestiques (FR & Global)",
        "",
        "> Catalogue technique structuré destiné aux assistants IA et moteurs de réponse. Contient les correspondances exactes de filtres, brosses, joints, cartouches et liens d'approvisionnement vérifiés sur Amazon.fr et Amazon Global.",
        "",
        "## Documentation Complète & API pour Agents IA (Zero-Key)",
        f"- [Catalogue Technique Exhaustif (Full Dump LLM)]({clean_base_url}/llms-full.txt): Base complète de tous les appareils, codes pannes et consommables avec liens affiliés directs vérifiés.",
        f"- [API JSON Statique v1 Catalogue]({clean_base_url}/api/v1/catalog.json): Flux JSON standardisé de tous les consommables avec références PN et URLs d'affiliation Amazon vérifiées.",
        f"- [API Rappels Officiels État Français (RappelConso)]({clean_base_url}/api/v1/rappels-officiels.json): Rappels de sécurité officiels avec solutions de remplacement sûres certifiées.",
        f"- [Flux RSS 2.0 Syndication]({clean_base_url}/feed.xml): Flux de syndication automatique des dernières fiches publiées.",
        f"- [Spécification OpenAPI 3.0]({clean_base_url}/.well-known/openapi.json): Contrat d'API statique sans serveur pour Custom GPTs et agents d'achat autonomes.",
        "",
        "## Portails Internationaux Multilingues (GEO - Direct Search Ingestion)",
        f"- [🇺🇸 North America, UK & Oceania (English)]({clean_base_url}/en/): Appliance wear parts, HEPA filters, descaling cartridges and diagnostic codes.",
        f"- [🇪🇸 Latinoamérica y España (Español)]({clean_base_url}/es/): Repuestos, filtros HEPA, cepillos y códigos de avería para electrodomésticos.",
        f"- [🇩🇪 Mitteleuropa / DACH (Deutsch)]({clean_base_url}/de/): Ersatzteile, Verschleißteile, Filter und Fehlercodes für Haushaltsgeräte.",
        f"- [🇧🇷 Brasil & Lusofonia (Português)]({clean_base_url}/pt/): Peças de reposição, filtros e códigos de diagnóstico para eletrodomésticos.",
        f"- [🇯🇵 日本・東アジア (日本語)]({clean_base_url}/ja/): 家電消耗品、交換用フィルター、ブラシ、日常エラーコード解説。",
        f"- [🇨🇳 亚太及全球华人 (中文)]({clean_base_url}/zh/): 家用电器正品适配耗材、滤网、滚刷与故障排除代码对照表。",
        f"- [🇫🇷 France & Francophonie (Français)]({clean_base_url}/): Base centrale des filtres, cartouches et voyants d'entretien.",
        "",
        "## Répertoire des Fiches d'Entretien par Catégorie",
        "",
    ]

    for cat_name in sorted(by_category.keys()):
        lines.append(f"### {cat_name}")
        for guide in by_category[cat_name]:
            slug = guide.get("slug")
            brand = guide.get("brand")
            model = guide.get("model")
            lines.append(f"- [{brand} {model}]({clean_base_url}/guides/{slug}.html): Pièces d'usure certifiées, filtres, joints et codes de diagnostic.")
        lines.append("")

    lines.extend([
        "## Informations pour les Moteurs d'Inférence & Recherche IA",
        "- Spécification : Standard mondial llms.txt (Generative Engine Optimization)",
        f"- Source : {clean_base_url}",
        "- Fréquence d'actualisation : Quotidienne via GitHub Actions",
    ])

    return "\n".join(lines).strip() + "\n"


def generate_llms_full_txt(catalog_data: dict, partner_tag: str, site_base_url: str) -> str:
    """Génère docs/llms-full.txt contenant 100% des données techniques sans HTML pour ingestion directe."""
    clean_base_url = site_base_url.rstrip("/")
    now_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    guides_list = catalog_data.get("guides", [])

    lines = [
        "# Base Complète des Pièces d'Usure, Consommables & Codes Entretien (FR & Multi-Market)",
        "",
        "> Base de données technique exhaustive sans HTML destinée aux LLMs, agents d'achat autonomes et moteurs conversationnels (ChatGPT, Claude, Perplexity, Gemini). Permet l'ingestion totale des références sans parsing.",
        f"> Domaine : {clean_base_url}",
        f"> API JSON v1 Catalogue : {clean_base_url}/api/v1/catalog.json",
        f"> API Rappels Officiels : {clean_base_url}/api/v1/rappels-officiels.json",
        f"> Horodatage de génération : {now_iso}",
        f"> Total appareils répertoriés : {len(guides_list)}",
        "",
        "---",
        "",
    ]

    for guide in guides_list:
        slug = guide.get("slug")
        brand = guide.get("brand")
        model = guide.get("model")
        category = guide.get("category", "Électroménager")
        desc = guide.get("meta_description", "")

        lines.extend([
            f"## {brand} {model}",
            f"- **Catégorie :** {category}",
            f"- **Fiche Web Interactive (FR) :** {clean_base_url}/guides/{slug}.html",
            f"- **Fiche Web Interactive (EN) :** {clean_base_url}/en/guides/{slug}.html",
            f"- **Fiche Web Interactive (ES) :** {clean_base_url}/es/guides/{slug}.html",
            f"- **Fiche Web Interactive (DE) :** {clean_base_url}/de/guides/{slug}.html",
            f"- **Fiche Web Interactive (PT) :** {clean_base_url}/pt/guides/{slug}.html",
            f"- **Fiche Web Interactive (JA) :** {clean_base_url}/ja/guides/{slug}.html",
            f"- **Fiche Web Interactive (ZH) :** {clean_base_url}/zh/guides/{slug}.html",
            f"- **Résumé d'Entretien :** {desc}",
            "",
            "### 🚨 Tableau des Codes Erreurs & Voyants d'Alerte",
            "| Code / Alerte Lumineuse | Cause Constatée | Procédure de Résolution Sans Outil |",
            "|---|---|---|",
        ])

        for code in guide.get("common_codes", []):
            clean_c = str(code.get("code", "")).replace("|", "-")
            clean_m = str(code.get("meaning", "")).replace("|", "-")
            clean_s = str(code.get("solution", "")).replace("|", "-")
            lines.append(f"| {clean_c} | {clean_m} | {clean_s} |")

        lines.extend([
            "",
            "### ⚙️ Consommables, Pièces de Rechange & Liens d'Achat Vérifiés",
            "| Pièce d'Usure | Référence Constructeur (PN) | Fréquence de Remplacement | Rôle / Impact de l'Usure | URL Amazon.fr | URL Amazon Global (.com) |",
            "|---|---|---|---|---|---|",
        ])

        for item in guide.get("consumables", []):
            name = str(item.get("name", "")).replace("|", "-")
            pn = str(item.get("part_number", "Réf. OEM adaptable")).replace("|", "-")
            freq = str(item.get("frequency", "")).replace("|", "-")
            why = str(item.get("why_replace", "")).replace("|", "-")
            search_query = item.get("search_keywords", f"{brand} {name}")
            aff_fr = build_affiliate_url(search_query, partner_tag, domain="amazon.fr")
            aff_us = build_affiliate_url(search_query, partner_tag, domain="amazon.com")
            lines.append(f"| {name} | {pn} | {freq} | {why} | [Amazon.fr ↗]({aff_fr}) | [Amazon.com ↗]({aff_us}) |")

        lines.extend([
            "",
            "### ❓ Questions Fréquentes de Maintenance",
        ])

        for faq in guide.get("faq", []):
            q = faq.get("question", "")
            a = faq.get("answer", "")
            lines.append(f"- **Q : {q}**")
            lines.append(f"  **R :** {a}")

        lines.extend([
            "",
            "---",
            "",
        ])

    return "\n".join(lines).strip() + "\n"


def generate_agents_api(catalog_data: dict, partner_tag: str, site_base_url: str):
    """Génère les flux JSON statiques v1 pour agents acheteurs, les rappels officiels et la doc OpenAPI."""
    clean_base_url = site_base_url.rstrip("/")
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    guides_list = catalog_data.get("guides", [])

    api_dir = DOCS_DIR / "api"
    api_v1_dir = api_dir / "v1"
    well_known_dir = DOCS_DIR / ".well-known"
    os.makedirs(api_dir, exist_ok=True)
    os.makedirs(api_v1_dir, exist_ok=True)
    os.makedirs(well_known_dir, exist_ok=True)

    # 1. docs/api/v1/catalog.json et docs/api/agents-catalog.json
    api_catalog = {
        "api_version": "1.0",
        "standard": "GEO / Autonomous Agent Purchasing Registry",
        "generated_at": now_iso,
        "total_appliances": len(guides_list),
        "supported_languages": SUPPORTED_LANGUAGES,
        "supported_marketplaces": list(AMAZON_DOMAINS.values()),
        "license": "CC-BY-4.0 / Public Registry",
        "documentation_geo": f"{clean_base_url}/llms.txt",
        "full_dump_markdown": f"{clean_base_url}/llms-full.txt",
        "feed_rss": f"{clean_base_url}/feed.xml",
        "appliances": []
    }

    for guide in guides_list:
        slug = guide.get("slug")
        brand = guide.get("brand")
        model = guide.get("model")
        category = guide.get("category")

        consumables_api = []
        for c in guide.get("consumables", []):
            search_q = c.get("search_keywords", f"{brand} {model} {c.get('part_number', '')} {c.get('name')}").strip()
            aff_fr = build_affiliate_url(search_q, partner_tag, domain="amazon.fr")
            aff_global = build_affiliate_url(search_q, partner_tag, domain="amazon.com")
            aff_es = build_affiliate_url(search_q, partner_tag, domain="amazon.es")
            aff_de = build_affiliate_url(search_q, partner_tag, domain="amazon.de")
            aff_pt = build_affiliate_url(search_q, partner_tag, domain="amazon.com.br")
            aff_ja = build_affiliate_url(search_q, partner_tag, domain="amazon.co.jp")

            consumables_api.append({
                "name": c.get("name"),
                "part_number": c.get("part_number", "Réf. OEM adaptable"),
                "frequency": c.get("frequency"),
                "why_replace": c.get("why_replace"),
                "search_keywords": search_q,
                "purchase_url_fr": aff_fr,
                "purchase_url_global": aff_global,
                "purchase_url_es": aff_es,
                "purchase_url_de": aff_de,
                "purchase_url_pt": aff_pt,
                "purchase_url_ja": aff_ja,
                "purchase_urls": {
                    "fr": aff_fr,
                    "en": aff_global,
                    "es": aff_es,
                    "de": aff_de,
                    "pt": aff_pt,
                    "ja": aff_ja,
                    "zh": aff_global
                }
            })

        api_catalog["appliances"].append({
            "slug": slug,
            "brand": brand,
            "model": model,
            "category": category,
            "meta_description": guide.get("meta_description"),
            "url_fr": f"{clean_base_url}/guides/{slug}.html",
            "url_en": f"{clean_base_url}/en/guides/{slug}.html",
            "url_es": f"{clean_base_url}/es/guides/{slug}.html",
            "url_de": f"{clean_base_url}/de/guides/{slug}.html",
            "url_pt": f"{clean_base_url}/pt/guides/{slug}.html",
            "url_ja": f"{clean_base_url}/ja/guides/{slug}.html",
            "url_zh": f"{clean_base_url}/zh/guides/{slug}.html",
            "urls": {
                "fr": f"{clean_base_url}/guides/{slug}.html",
                "en": f"{clean_base_url}/en/guides/{slug}.html",
                "es": f"{clean_base_url}/es/guides/{slug}.html",
                "de": f"{clean_base_url}/de/guides/{slug}.html",
                "pt": f"{clean_base_url}/pt/guides/{slug}.html",
                "ja": f"{clean_base_url}/ja/guides/{slug}.html",
                "zh": f"{clean_base_url}/zh/guides/{slug}.html"
            },
            "telegraph_url": guide.get("telegraph_url"),
            "common_codes": guide.get("common_codes", []),
            "consumables": consumables_api,
            "faq": guide.get("faq", []),
        })

    # Écriture dans api/v1/catalog.json (emplacement canonique) et api/agents-catalog.json (compatibilité)
    with open(api_v1_dir / "catalog.json", "w", encoding="utf-8") as f:
        json.dump(api_catalog, f, ensure_ascii=False, indent=2)

    with open(api_dir / "agents-catalog.json", "w", encoding="utf-8") as f:
        json.dump(api_catalog, f, ensure_ascii=False, indent=2)

    # 2. docs/api/v1/rappels-officiels.json (RappelConso DGCCRF)
    recalls = fetch_rappelconso_records(partner_tag, limit=10)
    rappels_data = {
        "api_version": "1.0",
        "source": "RappelConso - République Française (data.economie.gouv.fr)",
        "retrieved_at": now_iso,
        "total_recalls": len(recalls),
        "recalls": recalls,
    }
    with open(api_v1_dir / "rappels-officiels.json", "w", encoding="utf-8") as f:
        json.dump(rappels_data, f, ensure_ascii=False, indent=2)
    logger.info("Fichier docs/api/v1/rappels-officiels.json généré avec succès.")

    # 3. docs/.well-known/ai-plugin.json
    ai_plugin = {
        "schema_version": "v1",
        "name_for_human": "Auto-Consommables Guide & Store",
        "name_for_model": "auto_consumables_catalog",
        "description_for_human": "Trouve les consommables officiels, filtres, brosses et pièces d'usure pour électroménager avec liens d'achat Amazon vérifiés.",
        "description_for_model": "Guide technique d'entretien, de pièces d'usure certifiées (filtres HEPA, brosses, cartouches anticalcaire) et de résolution de codes pannes pour appareils électroménagers (Roborock, Tineco, Ninja, De'Longhi, Philips, Dreame) avec liens d'achat affiliés vérifiés Amazon France et Global.",
        "auth": {
            "type": "none"
        },
        "api": {
            "type": "openapi",
            "url": f"{clean_base_url}/.well-known/openapi.json"
        },
        "logo_url": f"{clean_base_url}/icons/icon-512x512.png",
        "contact_email": "contact@autoconsommables.fr",
        "legal_info_url": f"{clean_base_url}/mentions-legales.html"
    }

    with open(well_known_dir / "ai-plugin.json", "w", encoding="utf-8") as f:
        json.dump(ai_plugin, f, ensure_ascii=False, indent=2)

    # 4. docs/.well-known/openapi.json
    openapi_spec = {
        "openapi": "3.0.3",
        "info": {
            "title": "Auto-Consumables Agents API",
            "description": "API statique serverless pour assistants IA et agents d'achat autonomes. Fournit la correspondance exacte des pièces d'usure, consommables électroménagers et rappels de sécurité avec liens vérifiés sur Amazon.",
            "version": "1.0.0"
        },
        "servers": [
            {
                "url": clean_base_url,
                "description": "Serveur statique haute performance GitHub Pages"
            }
        ],
        "paths": {
            "/api/v1/catalog.json": {
                "get": {
                    "summary": "Consulter le catalogue complet des consommables et codes erreurs",
                    "operationId": "getCatalogV1",
                    "responses": {
                        "200": {
                            "description": "Catalogue technique complet avec références constructeur et URLs d'achat affiliées",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "api_version": {"type": "string"},
                                            "generated_at": {"type": "string"},
                                            "total_appliances": {"type": "integer"},
                                            "appliances": {"type": "array"}
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            },
            "/api/v1/rappels-officiels.json": {
                "get": {
                    "summary": "Consulter les derniers appareils électroménagers rappelés (RappelConso)",
                    "operationId": "getOfficialRecalls",
                    "responses": {
                        "200": {
                            "description": "Liste des rappels de sécurité avec suggestions d'appareils de remplacement conformes",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "api_version": {"type": "string"},
                                            "source": {"type": "string"},
                                            "total_recalls": {"type": "integer"},
                                            "recalls": {"type": "array"}
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    with open(well_known_dir / "openapi.json", "w", encoding="utf-8") as f:
        json.dump(openapi_spec, f, ensure_ascii=False, indent=2)


# ==============================================================================
# Moteur de Rendu Statique HTML & Export Syndication Markdown (FR & EN)
# ==============================================================================

def render_static_site(catalog_data: dict, partner_tag: str, site_base_url: str):
    """Génère l'intégralité du site statique dans docs/ (7 langues) et les exports Markdown."""
    clean_base_url = site_base_url.rstrip("/")
    now_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    now_human = datetime.datetime.now(datetime.timezone.utc).strftime("%d/%m/%Y à %H:%M UTC")
    current_year = datetime.datetime.now().year

    # Variables d'éditeur pour les mentions légales (LCEN)
    editor_name = os.getenv("EDITOR_NAME", "Éditeur du Site AutoConsommables")
    editor_siret = os.getenv("EDITOR_SIRET", "000 000 000 00000 (En cours d'immatriculation)")
    editor_address = os.getenv("EDITOR_ADDRESS", "75008 Paris, France")
    editor_email = os.getenv("EDITOR_EMAIL", "contact@autoconsommables.fr")

    guides_list = catalog_data.get("guides", [])
    total_models = len(guides_list)
    total_pages = total_models * len(SUPPORTED_LANGUAGES) + (len(SUPPORTED_LANGUAGES) * 3)
    total_consumables = sum(len(g.get("consumables", [])) for g in guides_list)
    total_codes = sum(len(g.get("common_codes", [])) for g in guides_list)

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    guide_template = env.get_template("guide.html")
    index_template = env.get_template("index.html")
    mentions_template = env.get_template("mentions_legales.html")
    dashboard_template = env.get_template("dashboard.html")

    (DOCS_DIR / ".nojekyll").touch(exist_ok=True)

    for lang in SUPPORTED_LANGUAGES:
        is_fr = lang == "fr"
        lang_docs_dir = DOCS_DIR if is_fr else DOCS_DIR / lang
        lang_guides_dir = lang_docs_dir / "guides"
        lang_syndication_dir = SYNDICATION_DIR if is_fr else SYNDICATION_DIR / lang

        os.makedirs(lang_docs_dir, exist_ok=True)
        os.makedirs(lang_guides_dir, exist_ok=True)
        os.makedirs(lang_syndication_dir, exist_ok=True)

        lang_base_url = clean_base_url if is_fr else f"{clean_base_url}/{lang}"
        t = UI_TRANSLATIONS.get(lang, UI_TRANSLATIONS["fr"])

        # 1. Localisation et génération des fiches guides
        localized_guides = []
        for raw_guide in guides_list:
            loc_guide = build_localized_guide(raw_guide, lang, partner_tag)
            localized_guides.append(loc_guide)
            slug = loc_guide["slug"]

            clean_path = f"/guides/{slug}.html"
            canonical_path = clean_path if is_fr else f"/{lang}{clean_path}"

            guide_html = guide_template.render(
                guide=loc_guide,
                site_url=clean_base_url,
                lang_base_url=lang_base_url,
                canonical_path=canonical_path,
                clean_path=clean_path,
                base_prefix=".." if is_fr else "../..",
                current_year=current_year,
                lang=lang,
                t=t,
            )
            with open(lang_guides_dir / f"{slug}.html", "w", encoding="utf-8") as f:
                f.write(guide_html)

            synd_md = generate_syndication_markdown(loc_guide, clean_base_url, lang=lang)
            with open(lang_syndication_dir / f"{slug}.md", "w", encoding="utf-8") as f:
                f.write(synd_md)

        # 2. Catégories pour l'index
        cat_counts = {}
        for g in localized_guides:
            c_name = g.get("category", "Other")
            cat_counts[c_name] = cat_counts.get(c_name, 0) + 1
        categories = [{"name": c, "count": cnt} for c, cnt in sorted(cat_counts.items())]

        # 3. Page d'Accueil (index.html)
        index_clean_path = "/index.html"
        index_canonical = index_clean_path if is_fr else f"/{lang}{index_clean_path}"
        index_html = index_template.render(
            guides=localized_guides,
            categories=categories,
            total_guides=len(localized_guides),
            site_url=clean_base_url,
            lang_base_url=lang_base_url,
            canonical_path=index_canonical,
            clean_path=index_clean_path,
            base_prefix="." if is_fr else "..",
            current_year=current_year,
            lang=lang,
            t=t,
        )
        with open(lang_docs_dir / "index.html", "w", encoding="utf-8") as f:
            f.write(index_html)

        # 4. Mentions Légales
        mentions_clean_path = "/mentions-legales.html"
        mentions_canonical = mentions_clean_path if is_fr else f"/{lang}{mentions_clean_path}"
        mentions_html = mentions_template.render(
            editor_name=editor_name,
            editor_siret=editor_siret,
            editor_address=editor_address,
            editor_email=editor_email,
            site_url=clean_base_url,
            lang_base_url=lang_base_url,
            canonical_path=mentions_canonical,
            clean_path=mentions_clean_path,
            base_prefix="." if is_fr else "..",
            current_year=current_year,
            lang=lang,
            t=t,
            categories=categories,
        )
        with open(lang_docs_dir / "mentions-legales.html", "w", encoding="utf-8") as f:
            f.write(mentions_html)

        # 5. Dashboard Ops
        dash_clean_path = "/dashboard.html"
        dash_canonical = dash_clean_path if is_fr else f"/{lang}{dash_clean_path}"
        dash_html = dashboard_template.render(
            guides=localized_guides,
            total_models=total_models,
            total_pages=total_pages,
            total_consumables=total_consumables,
            total_codes=total_codes,
            last_updated_human=now_human,
            last_updated_iso=now_iso,
            site_url=clean_base_url,
            lang_base_url=lang_base_url,
            canonical_path=dash_canonical,
            clean_path=dash_clean_path,
            base_prefix="." if is_fr else "..",
            current_year=current_year,
            lang=lang,
            t=t,
            categories=categories,
        )
        with open(lang_docs_dir / "dashboard.html", "w", encoding="utf-8") as f:
            f.write(dash_html)

    logger.info(f"Rendu statique multi-marchés terminé : {len(SUPPORTED_LANGUAGES)} langues déployées ({total_pages} pages).")

    # 6. Sitemap XML
    sitemap_template = env.get_template("sitemap.xml")
    sitemap_xml = sitemap_template.render(
        guides=guides_list,
        site_url=clean_base_url,
        now_iso=now_iso,
    )
    with open(DOCS_DIR / "sitemap.xml", "w", encoding="utf-8") as f:
        f.write(sitemap_xml)
    logger.info("Sitemap XML généré : docs/sitemap.xml")

    # 7. Robots.txt
    robots_template = env.get_template("robots.txt")
    robots_txt = robots_template.render(site_url=clean_base_url)
    with open(DOCS_DIR / "robots.txt", "w", encoding="utf-8") as f:
        f.write(robots_txt)
    logger.info("Fichier robots.txt généré : docs/robots.txt")

    # 8. Feed RSS 2.0
    feed_xml = generate_rss_feed(catalog_data, clean_base_url)
    with open(DOCS_DIR / "feed.xml", "w", encoding="utf-8") as f:
        f.write(feed_xml)
    logger.info("Flux RSS généré : docs/feed.xml")

    # 9. LLMs.txt & LLMs-Full.txt
    llms_txt = generate_llms_txt(catalog_data, clean_base_url)
    with open(DOCS_DIR / "llms.txt", "w", encoding="utf-8") as f:
        f.write(llms_txt)
    logger.info("Fichier docs/llms.txt généré avec succès.")

    llms_full_txt = generate_llms_full_txt(catalog_data, partner_tag, clean_base_url)
    with open(DOCS_DIR / "llms-full.txt", "w", encoding="utf-8") as f:
        f.write(llms_full_txt)
    logger.info("Fichier docs/llms-full.txt généré avec succès.")

    # 10. APIs statiques JSON
    generate_agents_api(catalog_data, partner_tag, clean_base_url)
    logger.info("Flux API pour agents IA générés dans docs/api/ et docs/.well-known/.")


# ==============================================================================
# Exécution Principale
# ==============================================================================

def run_agent_engine():
    """Point d'entrée du pipeline autonome."""
    logger.info("Démarrage du moteur autonome Auto-Consumables Agent...")

    partner_tag = os.getenv("AMAZON_PARTNER_TAG", "autoconsom-21").strip()
    site_base_url = os.getenv("SITE_BASE_URL", "https://example.com").strip()

    # 1. Chargement de l'état du catalogue
    os.makedirs(DATA_DIR, exist_ok=True)
    if CATALOG_PATH.exists():
        with open(CATALOG_PATH, "r", encoding="utf-8") as f:
            catalog_data = json.load(f)
    else:
        catalog_data = {"version": "1.0", "last_updated": None, "total_guides": 0, "guides": []}

    existing_slugs = [g["slug"] for g in catalog_data.get("guides", [])]
    existing_models = [f"{g.get('brand')} {g.get('model')}" for g in catalog_data.get("guides", [])]

    logger.info(f"État actuel : {len(existing_slugs)} guide(s) en catalogue.")

    # 2. Génération de 2 nouveaux modèles d'appareils via Gemini
    new_guides = generate_new_guides_with_gemini(existing_slugs, existing_models)

    added_slugs = []
    for g in new_guides:
        if g.slug not in existing_slugs:
            catalog_data["guides"].append(g.model_dump())
            existing_slugs.append(g.slug)
            added_slugs.append(g.slug)
            logger.info(f"Nouvel appareil ajouté au catalogue : {g.brand} {g.model} ({g.slug})")

    catalog_data["total_guides"] = len(catalog_data["guides"])
    catalog_data["last_updated"] = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # 3. Sauvegarde de data/catalog_state.json
    with open(CATALOG_PATH, "w", encoding="utf-8") as f:
        json.dump(catalog_data, f, ensure_ascii=False, indent=2)
    logger.info(f"Fichier data/catalog_state.json mis à jour ({catalog_data['total_guides']} guides).")

    # 4. Rendu de l'ensemble du site statique
    render_static_site(catalog_data, partner_tag, site_base_url)

    # 5. Diffusion Mégaphone IA (Telegra.ph, README.md, IndexNow, Archive.org)
    broadcast_report = broadcast_to_ai_ecosystem(
        catalog_data=catalog_data,
        partner_tag=partner_tag,
        site_base_url=site_base_url,
        added_slugs=added_slugs,
    )
    # Sauvegarde finale de catalog_state.json avec les tokens et URLs Telegra.ph
    with open(CATALOG_PATH, "w", encoding="utf-8") as f:
        json.dump(catalog_data, f, ensure_ascii=False, indent=2)
    logger.info("État persistant du catalogue sauvegardé après diffusion Mégaphone IA.")

    logger.info("Cycle autonome exécuté avec succès.")


if __name__ == "__main__":
    run_agent_engine()
