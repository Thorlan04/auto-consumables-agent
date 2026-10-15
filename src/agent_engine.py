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

from jinja2 import Environment, FileSystemLoader
from pydantic import BaseModel, Field

# Chargement d'éventuelles variables .env locales
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from indexnow_ping import ensure_indexnow_key_file, ping_indexnow

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
  Exemples de précision exigée :
  * Tineco Floor One Switch S7 (FW210100EU)
  * Ninja DoubleStack XL 9,5L (SL400EU)
  * De'Longhi Rivelia (FEAM 44.55.B)
  * Roborock Qrevo Curv (QRC02-00)
  * Dreame X40 Ultra Complete
  * Breville Barista Touch Impress (BES881BSS)
  * Shark Stratos Cordless Pet Pro (IZ400EU / IZ400UK)
  * Dyson V15s Detect Submarine (SV47)
  * Philips LatteGo Série 5400 (EP5447/90)
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


CATEGORY_EN_MAP = {
    "Aspirateurs Laveurs": "Wet & Dry Vacuums",
    "Machines à Café à Grains": "Bean-to-Cup Coffee Machines",
    "Robots Aspirateurs": "Robot Vacuums & Mops",
    "Friteuses sans Huile (Air Fryer)": "Air Fryers",
    "Purificateurs d'Air": "Air Purifiers",
    "Centrales Vapeur": "Steam Generator Irons",
}


def build_english_guide(guide: dict, partner_tag: str) -> dict:
    """Adapte une fiche technique en version anglaise pour les marchés USA / UK / Global."""
    en_cat = CATEGORY_EN_MAP.get(guide.get("category", ""), guide.get("category", "Home Appliances"))
    en_title = f"{guide.get('brand')} {guide.get('model')}: Replacement Parts, Filters & Error Codes"
    en_desc = f"Genuine OEM replacement filters, brushes, descaling cartridges and routine error codes guide for {guide.get('brand')} {guide.get('model')}."

    en_consumables = []
    for c in guide.get("consumables", []):
        search_q = f"{guide.get('brand')} {guide.get('model')} {c.get('part_number', '')} {c.get('name')}".strip()
        en_consumables.append({
            "name": c.get("name"),
            "part_number": c.get("part_number", "OEM compatible"),
            "frequency": c.get("frequency"),
            "why_replace": c.get("why_replace"),
            "search_keywords": search_q,
            "affiliate_url": build_affiliate_url(search_q, partner_tag, domain="amazon.com"),
        })

    return {
        "slug": guide["slug"],
        "title": en_title,
        "brand": guide["brand"],
        "model": guide["model"],
        "category": en_cat,
        "meta_description": en_desc,
        "common_codes": guide.get("common_codes", []),
        "consumables": en_consumables,
        "faq": guide.get("faq", []),
    }


def generate_syndication_markdown(guide: dict, site_base_url: str, lang: str = "fr") -> str:
    """Génère un export Markdown propre prêt pour la syndication sur dev.to, Medium ou blogs techniques."""
    is_en = lang == "en"
    canonical_path = f"/en/guides/{guide['slug']}.html" if is_en else f"/guides/{guide['slug']}.html"
    canonical_url = f"{site_base_url.rstrip('/')}{canonical_path}"
    date_str = datetime.datetime.now().strftime("%Y-%m-%d")

    title = guide["title"]
    desc = guide.get("meta_description", "")

    lines = [
        "---",
        f'title: "{title}"',
        f'description: "{desc}"',
        f'canonical_url: "{canonical_url}"',
        f'published_at: "{date_str}"',
        'tags: ["diy", "guide", "appliances", "maintenance", "tech"]' if is_en else 'tags: ["diy", "guide", "electromenager", "entretien", "tech"]',
        "---",
        "",
        f"# {title}",
        "",
        "> **Amazon Associates Disclosure:** This independent article contains affiliate links (#AffiliateLink). As an Amazon Associate, we earn from qualifying purchases at no extra cost to you." if is_en else "> **Transparence Partenaire Amazon :** Cet article indépendant comporte des liens affiliés Amazon France (#LienAffilié). En tant que Partenaire Amazon, nous réalisons un bénéfice sur les achats éligibles sans surcoût pour vous.",
        f"> *Interactive guide available at: [{canonical_url}]({canonical_url})*" if is_en else f"> *Source originale et guide interactif : [{canonical_url}]({canonical_url})*",
        "",
        "## ⚠️ Safety & Preliminary Disclaimers" if is_en else "## ⚠️ Sécurité & Consignes Préalables",
        "Always unplug your appliance before performing maintenance. These procedures strictly cover routine maintenance and tool-free wear parts." if is_en else "Débranchez impérativement votre appareil avant toute intervention. Les procédures ci-dessous ne concernent que l'entretien courant et les pièces d'usure amovibles sans outillage.",
        "",
        "## 🛠️ Parts Cross-Reference & Wear Chart" if is_en else "## 🛠️ Table de Correspondances des Pièces & Consommables Certifiés",
        "",
        "| Genuine Part / Accessory | Manufacturer PN | Replacement Interval | Check Availability |" if is_en else "| Pièce / Accessoire d'Origine | Réf. Constructeur (PN) | Fréquence de Remplacement | Disponibilité & Référence Vérifiée |",
        "| :--- | :--- | :--- | :--- |",
    ]

    for item in guide.get("consumables", []):
        pn = item.get("part_number") or "OEM compatible"
        url = item.get("affiliate_url", "")
        btn_txt = "Check Amazon Stock ↗" if is_en else "Vérifier le stock Amazon France ↗"
        lines.append(f"| **{item.get('name')}** | `{pn}` | {item.get('frequency')} | [{btn_txt}]({url}) |")

    lines.extend([
        "",
        "### 🔍 Detailed Wear-Part Analysis" if is_en else "### 🔍 Analyse Technique des Pièces d'Usure",
        "",
    ])

    for item in guide.get("consumables", []):
        lines.append(f"#### {item.get('name')}")
        lines.append(f"- **Part Number (PN):** `{item.get('part_number', 'OEM compatible')}`" if is_en else f"- **Référence Fabricant (PN) :** `{item.get('part_number', 'Réf. OEM adaptable')}`")
        lines.append(f"- **Recommended Interval:** {item.get('frequency')}" if is_en else f"- **Fréquence recommandée :** {item.get('frequency')}")
        lines.append(f"- **Critical Impact:** {item.get('why_replace')}" if is_en else f"- **Pourquoi est-ce critique ?** {item.get('why_replace')}")
        lines.append(f"- **Amazon Link:** [View genuine part on Amazon ↗]({item.get('affiliate_url')})" if is_en else f"- **Lien direct pièces adaptées :** [Accéder à la référence sur Amazon.fr ↗]({item.get('affiliate_url')})")
        lines.append("")

    lines.extend([
        "## 🚨 Error Codes & Maintenance Alerts" if is_en else "## 🚨 Codes Erreurs & Voyants d'Alerte Fréquents",
        "",
    ])

    for code in guide.get("common_codes", []):
        lines.append(f"### ⚠️ {code.get('code')}")
        lines.append(f"- **Root Cause:** {code.get('meaning')}" if is_en else f"- **Cause courante :** {code.get('meaning')}")
        lines.append(f"- **Tool-Free Resolution:** {code.get('solution')}" if is_en else f"- **Procédure de résolution sans outil :** {code.get('solution')}")
        lines.append("")

    lines.extend([
        "## ❓ Frequently Asked Questions (FAQ)" if is_en else "## ❓ Questions Fréquentes (FAQ)",
        "",
    ])

    for faq in guide.get("faq", []):
        lines.append(f"### Q: {faq.get('question')}" if is_en else f"### Q : {faq.get('question')}")
        lines.append(f"**A:** {faq.get('answer')}" if is_en else f"**R :** {faq.get('answer')}")
        lines.append("")

    lines.extend([
        "---",
        f"*Maintenance datasheet generated for **{guide.get('brand')} {guide.get('model')}** — Read interactive guide at [{canonical_url}]({canonical_url}).*" if is_en else f"*Fiche technique rédigée pour le modèle **{guide.get('brand')} {guide.get('model')}** — Retrouvez la version interactive en ligne sur [AutoConsommables.fr]({canonical_url}).*",
    ])

    return "\n".join(lines)


# ==============================================================================
# Moteur de Rendu Statique HTML & Export Syndication Markdown (FR & EN)
# ==============================================================================

def render_static_site(catalog_data: dict, partner_tag: str, site_base_url: str):
    """Génère l'intégralité du site statique dans docs/ (FR + EN) et les exports Markdown."""
    # Dossiers français
    os.makedirs(DOCS_DIR, exist_ok=True)
    os.makedirs(GUIDES_DIR, exist_ok=True)
    os.makedirs(SYNDICATION_DIR, exist_ok=True)

    # Dossiers anglais (International USA / UK)
    docs_en_dir = DOCS_DIR / "en"
    guides_en_dir = docs_en_dir / "guides"
    syndication_en_dir = SYNDICATION_DIR / "en"
    os.makedirs(docs_en_dir, exist_ok=True)
    os.makedirs(guides_en_dir, exist_ok=True)
    os.makedirs(syndication_en_dir, exist_ok=True)

    # Désactiver le traitement Jekyll pour que GitHub Pages serve directement tous les dossiers (en/, guides/, etc.)
    (DOCS_DIR / ".nojekyll").touch(exist_ok=True)

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )

    clean_base_url = site_base_url.rstrip("/")
    now_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    current_year = datetime.datetime.now().year

    # Variables d'éditeur pour les mentions légales (LCEN)
    editor_name = os.getenv("EDITOR_NAME", "Éditeur du Site AutoConsommables")
    editor_siret = os.getenv("EDITOR_SIRET", "000 000 000 00000 (En cours d'immatriculation)")
    editor_address = os.getenv("EDITOR_ADDRESS", "75008 Paris, France")
    editor_email = os.getenv("EDITOR_EMAIL", "contact@autoconsommables.fr")

    guides_list = catalog_data.get("guides", [])

    # 1. Mise à jour des URLs d'affiliation Amazon France
    for guide in guides_list:
        for consumable in guide.get("consumables", []):
            search_query = consumable.get("search_keywords", f"{guide.get('brand')} {consumable.get('name')}")
            consumable["affiliate_url"] = build_affiliate_url(search_query, partner_tag, domain="amazon.fr")

    # 2. Génération des pages guides FR (docs/guides/{slug}.html) + Syndication FR
    guide_template = env.get_template("guide.html")
    for guide in guides_list:
        guide_slug = guide["slug"]
        guide_html = guide_template.render(
            guide=guide,
            site_url=clean_base_url,
            canonical_path=f"/guides/{guide_slug}.html",
            base_prefix="..",
            current_year=current_year,
            lang="fr",
        )
        with open(GUIDES_DIR / f"{guide_slug}.html", "w", encoding="utf-8") as f:
            f.write(guide_html)

        syndication_md = generate_syndication_markdown(guide, clean_base_url, lang="fr")
        with open(SYNDICATION_DIR / f"{guide_slug}.md", "w", encoding="utf-8") as f:
            f.write(syndication_md)

    # 3. Génération des pages guides EN (docs/en/guides/{slug}.html) + Syndication EN
    en_guides_list = []
    for guide in guides_list:
        guide_slug = guide["slug"]
        en_guide = build_english_guide(guide, partner_tag)
        en_guides_list.append(en_guide)

        guide_en_html = guide_template.render(
            guide=en_guide,
            site_url=clean_base_url,
            canonical_path=f"/en/guides/{guide_slug}.html",
            base_prefix="../..",
            current_year=current_year,
            lang="en",
        )
        with open(guides_en_dir / f"{guide_slug}.html", "w", encoding="utf-8") as f:
            f.write(guide_en_html)

        syndication_en_md = generate_syndication_markdown(en_guide, clean_base_url, lang="en")
        with open(syndication_en_dir / f"{guide_slug}.md", "w", encoding="utf-8") as f:
            f.write(syndication_en_md)

    logger.info(f"{len(guides_list)} fiches générées en français ET en anglais (Total : {len(guides_list)*2} pages HTML).")

    # 4. Statistiques des catégories FR et EN
    cat_counts_fr = {}
    for g in guides_list:
        cat = g.get("category", "Autres")
        cat_counts_fr[cat] = cat_counts_fr.get(cat, 0) + 1
    categories_fr = [{"name": cat, "count": count} for cat, count in sorted(cat_counts_fr.items())]

    cat_counts_en = {}
    for g in en_guides_list:
        cat = g.get("category", "Other")
        cat_counts_en[cat] = cat_counts_en.get(cat, 0) + 1
    categories_en = [{"name": cat, "count": count} for cat, count in sorted(cat_counts_en.items())]

    # 5. Page d'Accueil FR (docs/index.html) & EN (docs/en/index.html)
    index_template = env.get_template("index.html")
    index_fr_html = index_template.render(
        guides=guides_list,
        categories=categories_fr,
        total_guides=len(guides_list),
        site_url=clean_base_url,
        canonical_path="/index.html",
        base_prefix=".",
        current_year=current_year,
        lang="fr",
    )
    with open(DOCS_DIR / "index.html", "w", encoding="utf-8") as f:
        f.write(index_fr_html)

    index_en_html = index_template.render(
        guides=en_guides_list,
        categories=categories_en,
        total_guides=len(en_guides_list),
        site_url=clean_base_url,
        canonical_path="/en/index.html",
        base_prefix="..",
        current_year=current_year,
        lang="en",
    )
    with open(docs_en_dir / "index.html", "w", encoding="utf-8") as f:
        f.write(index_en_html)

    # 6. Mentions Légales FR (docs/mentions-legales.html) & EN (docs/en/mentions-legales.html)
    mentions_template = env.get_template("mentions_legales.html")
    mentions_fr_html = mentions_template.render(
        editor_name=editor_name,
        editor_siret=editor_siret,
        editor_address=editor_address,
        editor_email=editor_email,
        site_url=clean_base_url,
        canonical_path="/mentions-legales.html",
        base_prefix=".",
        current_year=current_year,
        lang="fr",
    )
    with open(DOCS_DIR / "mentions-legales.html", "w", encoding="utf-8") as f:
        f.write(mentions_fr_html)

    mentions_en_html = mentions_template.render(
        editor_name=editor_name,
        editor_siret=editor_siret,
        editor_address=editor_address,
        editor_email=editor_email,
        site_url=clean_base_url,
        canonical_path="/en/mentions-legales.html",
        base_prefix="..",
        current_year=current_year,
        lang="en",
    )
    with open(docs_en_dir / "mentions-legales.html", "w", encoding="utf-8") as f:
        f.write(mentions_en_html)
    logger.info("Pages mentions légales générées (FR et EN).")

    # 6. Génération de docs/sitemap.xml
    sitemap_template = env.get_template("sitemap.xml")
    sitemap_xml = sitemap_template.render(
        guides=guides_list,
        site_url=clean_base_url,
        now_iso=now_iso,
    )
    with open(DOCS_DIR / "sitemap.xml", "w", encoding="utf-8") as f:
        f.write(sitemap_xml)
    logger.info("Sitemap XML généré : docs/sitemap.xml")

    # 7. Génération de docs/robots.txt
    robots_template = env.get_template("robots.txt")
    robots_txt = robots_template.render(site_url=clean_base_url)
    with open(DOCS_DIR / "robots.txt", "w", encoding="utf-8") as f:
        f.write(robots_txt)
    logger.info("Fichier robots.txt généré : docs/robots.txt")


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

    # 5. Déclaration de propriété IndexNow et Ping SEO
    indexnow_key = os.getenv("INDEXNOW_KEY", "7b9d64f028e14674a9844c3569bf12a1")
    ensure_indexnow_key_file(str(DOCS_DIR), indexnow_key)

    urls_to_ping = [
        f"{site_base_url.rstrip('/')}/index.html",
        f"{site_base_url.rstrip('/')}/en/index.html",
    ]
    for slug in added_slugs:
        urls_to_ping.append(f"{site_base_url.rstrip('/')}/guides/{slug}.html")
        urls_to_ping.append(f"{site_base_url.rstrip('/')}/en/guides/{slug}.html")

    ping_indexnow(site_base_url, urls_to_ping, indexnow_key)

    logger.info("Cycle autonome exécuté avec succès.")


if __name__ == "__main__":
    run_agent_engine()
