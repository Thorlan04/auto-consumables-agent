# Auto-Consumables Agent

Système 100% autonome et gratuit (0 € d'infrastructure) de génération de fiches pratiques d'entretien pour petit et gros électroménager grand public, couplé à un module comptable et fiscal certifié pour micro-entreprises françaises.

---

## Architecture du Projet

```
auto-consumables-agent/
│
├── .github/workflows/
│   └── autopilot.yml                # Workflow GitHub Actions autonome (exécuté toutes les 6h)
│
├── compta_impots/                   # MODULE FISCAL CONFIDENTIEL (Séparé du site public)
│   ├── livre_des_recettes_officiel.csv    # Registre obligatoire Art. L123-28 Code de Commerce
│   └── tableau_de_bord_fiscal.html        # Rapport visuel hors-ligne, calculs URSSAF & 2042-C-PRO
│
├── data/
│   └── catalog_state.json           # État persistant du catalogue (modèles, consommables, erreurs)
│
├── docs/                            # SITE STATIQUE DÉPLOYÉ SUR GITHUB PAGES
│   ├── guides/                      # Fiches pratiques HTML individuelles par appareil
│   ├── index.html                   # Accueil avec moteur de recherche instantané sans dépendance
│   ├── mentions-legales.html        # Mentions légales LCEN & Déclaration Partenaire Amazon
│   ├── sitemap.xml                  # Plan du site SEO pour les moteurs de recherche
│   ├── robots.txt                   # Directives d'indexation
│   └── <indexnow_key>.txt           # Validation de domaine protocole IndexNow
│
├── src/
│   ├── agent_engine.py              # Moteur autonome (Gemini 2.5 Flash + Jinja2 + Liens Amazon infaillibles)
│   ├── compta_manager.py            # CLI comptable pour enregistrer les virements et générer les bilans
│   └── indexnow_ping.py             # Ping automatique pour référencement immédiat (Bing, Yahoo, Qwant)
│
├── templates/                       # Gabarits HTML Jinja2 (Zero Tracker, Zero Cookie)
│   ├── base.html                    # Socle HTML commun avec bandeau de transparence DGCCRF
│   ├── guide.html                   # Gabarit de fiche appareil avec JSON-LD FAQPage & Breadcrumb
│   ├── index.html                   # Gabarit d'accueil avec recherche vanilla JS
│   ├── mentions_legales.html        # Gabarit juridique LCEN
│   ├── sitemap.xml                  # Gabarit sitemap
│   └── robots.txt                   # Gabarit robots
│
├── GUIDE_INSTALLATION_ET_IMPOTS.md  # Guide pas-à-pas d'installation et de télédéclaration fiscale
├── requirements.txt                 # Dépendances Python (google-genai, jinja2, requests, pydantic)
└── .gitignore                       # Protection des clés API et fichiers locaux
```

---

## Points Forts Techniques & Légaux

1. **Zéro Erreur 404 Amazon :** Aucune URL de produit ou ASIN inventé par l'IA. Les boutons génèrent des requêtes de recherche dynamiques encodées via `build_affiliate_url()` garantissant l'accès permanent aux consommables même en cas de rupture de stock ou de changement de référence constructeur.
2. **Conformité RGPD / CNIL :** Zéro cookie tiers, zéro script analytique invasif. Le site est 100% dispensé de bandeau de consentement aux cookies.
3. **Sécurité Matérielle Stricte :** Le prompt système de l'IA interdit formellement toute manipulation électrique interne ou dangereuse. Ne traite que les consommables remplaçables sans outil.
4. **Comptabilité Micro-Entreprise Conforme :** Livre des recettes au format de l'Article L123-28 du Code de commerce, ventilation par mois, par trimestre pour l'URSSAF et répartition automatique pour les cases **5KP**, **5TB**, **5HQ**, **5TE** du formulaire 2042-C-PRO des Impôts.

Consultez le fichier **[GUIDE_INSTALLATION_ET_IMPOTS.md](file:///D:/Agent%20Auto%20IA/GUIDE_INSTALLATION_ET_IMPOTS.md)** pour le déploiement immédiat.
