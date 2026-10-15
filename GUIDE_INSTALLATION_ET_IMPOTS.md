# Guide d'Installation, Déploiement & Conformité Fiscale Micro-Entreprise
**Projet : `auto-consumables-agent`**

Ce guide détaille pas-à-pas la mise en place à 0 € de votre écosystème autonome de fiches pratiques d'entretien électroménager et la gestion légale complète de vos revenus d'affiliation Amazon en micro-entreprise française.

---

## Sommaire
1. [Étape 1 : Obtention des Clés API et Paramétrage Amazon Partenaires](#étape-1--obtention-des-clés-api-et-paramétrage-amazon-partenaires)
2. [Étape 2 : Déploiement Gratuit sur GitHub Actions & GitHub Pages](#étape-2--déploiement-gratuit-sur-github-actions--github-pages)
3. [Étape 3 : Gestion Comptable et Déclarations Fiscales (URSSAF & 2042-C-PRO)](#étape-3--gestion-comptable-et-déclarations-fiscales-urssaf--2042-c-pro)
4. [Commandes Utiles et Routine Quotidienne](#commandes-utiles-et-routine-quotidienne)

---

## Étape 1 : Obtention des Clés API et Paramétrage Amazon Partenaires

### 1.1 Clé d'API Google Gemini (Gratuit)
Le moteur exploite le modèle `gemini-2.5-flash` via le SDK officiel `google-genai` pour identifier les appareils populaires et générer les diagnostics :
1. Rendez-vous sur le portail officiel [Google AI Studio](https://aistudio.google.com/).
2. Connectez-vous avec votre compte Google.
3. Cliquez sur le bouton bleu **« Get API key »** (en haut à gauche).
4. Cliquez sur **« Create API key »** dans un nouveau projet Google Cloud (gratuit, sans carte bancaire requise pour le palier gratuit standard).
5. Copiez votre clé d'API (elle ressemble à `AIzaSy...`). Conservez-la précieusement.

### 1.2 Compte et Paramétrage Amazon Partenaires (Club Partenaires France)
1. Rendez-vous sur [partenaires.amazon.fr](https://partenaires.amazon.fr/).
2. Si vous n'avez pas de compte, créez-en un en renseignant l'URL de votre site (ou l'URL future de votre GitHub Pages).
3. **Récupérer votre ID Partenaire (Tracking ID) :**  
   Il figure en haut à droite de votre tableau de bord (ex: `votreidentifiant-21`). C'est ce tag qui garantit que chaque clic vers Amazon vous rapporte une commission.
4. **Renseigner votre RIB (Paiement automatique par virement SEPA) :**
   - Cliquez sur votre adresse e-mail en haut à droite > **Paramètres du compte**.
   - Cliquez sur **« Modifier votre mode de paiement »**.
   - Sélectionnez **« Paiement par virement bancaire »** (seuil de paiement dès 25 € de gains).
   - Renseignez l'IBAN et le BIC du compte bancaire dédié à votre micro-entreprise.
   - Validez. Amazon émettra automatiquement un virement mensuel aux alentours du 20-25 de chaque mois pour les commissions acquises 60 jours plus tôt.

---

## Étape 2 : Déploiement Gratuit sur GitHub Actions & GitHub Pages

Le projet est conçu pour fonctionner **à vie sans aucun serveur payant** :
- Le code HTML statique est compilé dans le dossier `docs/`.
- GitHub Pages héberge le site gratuitement avec certificat SSL (HTTPS).
- GitHub Actions exécute le script Python toutes les 6 heures pour ajouter automatiquement 2 nouveaux modèles d'appareils et met à jour le site.

### 2.1 Pousser le code sur votre dépôt GitHub
1. Créez un nouveau dépôt sur [GitHub.com](https://github.com/new) (public ou privé).
2. Dans votre terminal, initialisez git et poussez le projet :
   ```bash
   git init
   git add .
   git commit -m "feat: initialisation auto-consumables-agent"
   git branch -M main
   git remote add origin https://github.com/<votre-pseudo>/auto-consumables-agent.git
   git push -u origin main
   ```

### 2.2 Activer l'hébergement gratuit GitHub Pages
1. Sur votre dépôt GitHub, allez dans l'onglet **Settings** (Paramètres).
2. Dans le menu de gauche, cliquez sur **Pages**.
3. Dans la section **Build and deployment** :
   - Source : **Deploy from a branch**
   - Branch : **main**
   - Folder : sélectionnez **`/docs`** (au lieu de `/root`).
4. Cliquez sur **Save**.
5. Après 1 à 2 minutes, GitHub Pages affiche l'URL publique de votre site :  
   `https://<votre-pseudo>.github.io/auto-consumables-agent/` (ou votre nom de domaine personnalisé si vous en associez un).

### 2.3 Configurer les Secrets GitHub (Variables d'Environnement)
Pour que GitHub Actions puisse exécuter `agent_engine.py` de manière autonome toutes les 6 heures :
1. Sur votre dépôt GitHub, allez dans **Settings** > **Secrets and variables** > **Actions**.
2. Cliquez sur **New repository secret** et ajoutez les variables suivantes :

| Nom du Secret | Description | Exemple de Valeur |
| :--- | :--- | :--- |
| `GEMINI_API_KEY` | Clé d'API obtenue sur Google AI Studio | `AIzaSyB123456789...` |
| `AMAZON_PARTNER_TAG` | Votre identifiant Partenaire Amazon | `monblog-21` |
| `SITE_BASE_URL` | URL publique de votre site GitHub Pages | `https://pseudo.github.io/auto-consumables-agent` |
| `EDITOR_NAME` | Nom et Prénom de l'exploitant (EI) | `Alexandre DUPONT` |
| `EDITOR_SIRET` | Numéro SIRET de votre micro-entreprise | `91234567800012` |
| `EDITOR_ADDRESS` | Adresse postale du siège social | `10 rue de la République, 75001 Paris` |
| `EDITOR_EMAIL` | Adresse e-mail de contact public | `contact@monsite.fr` |
| `INDEXNOW_KEY` | Clé pour le protocole IndexNow (Optionnel) | `7b9d64f028e14674a9844c3569bf12a1` |

Dès que ces secrets sont enregistrés, le workflow `.github/workflows/autopilot.yml` se déclenchera toutes les 6 heures (ou immédiatement en cliquant sur **Actions** > **Auto-Consumables Autopilot Pipeline** > **Run workflow**).

---

## Étape 3 : Gestion Comptable et Déclarations Fiscales (URSSAF & 2042-C-PRO)

> **Principe Légal Fondamental :**  
> En micro-entreprise, la fiscalité fonctionne selon une **comptabilité de trésorerie (ou d'encaissement)**.  
> Vous ne déclarez que les sommes **effectivement reçues sur votre compte bancaire**, et **jamais** les commissions "en attente" affichées sur Amazon.

Le dossier `compta_impots/` est strictement hors du dossier `docs/` pour garantir une confidentialité totale.

### 3.1 Enregistrer un virement perçu d'Amazon
À chaque fois qu'Amazon effectue un virement sur votre compte bancaire, enregistrez-le en une seule commande :

```bash
python src/compta_manager.py --add --date "2026-10-28" --montant 145.50 --ref "AMZ-2026-10"
```

Le script s'occupe de tout :
1. Il ajoute la ligne au format officiel dans `compta_impots/livre_des_recettes_officiel.csv` avec les mentions obligatoires :
   - Client : `Amazon Europe Core S.à r.l.`
   - Nature : `Commissions d'affiliation Amazon Partenaires`
   - Mode : `Virement SEPA`
2. Il trie automatiquement l'historique par ordre chronologique strict (Art. L123-28 du Code de commerce).
3. Il recalcule instantanément le rapport `compta_impots/tableau_de_bord_fiscal.html`.

### 3.2 Consulter le Tableau de Bord Fiscal Hors-Ligne
Double-cliquez simplement sur le fichier :
```
compta_impots/tableau_de_bord_fiscal.html
```
Il s'ouvre dans n'importe quel navigateur (sans connexion internet requise) et vous présente :
- Le total exact à reporter sur `autoentrepreneur.urssaf.fr` pour le trimestre ou le mois en cours.
- Le total annuel civil calculé du 01/01 au 31/12.
- Les cases exactes à cocher sur votre déclaration de revenus `2042-C-PRO`.
- Un bouton pour imprimer le Livre des Recettes officiel en PDF en cas de contrôle de l'URSSAF ou des Impôts.

---

### 3.3 Guide des Déclarations Officielles : Où reporter vos montants ?

#### A. Déclaration Périodique URSSAF (sur `autoentrepreneur.urssaf.fr`)
- **Périodicité :** Mensuelle (chaque fin de mois) ou Trimestrielle (30 avril, 31 juillet, 31 octobre, 31 janvier).
- **Ligne à remplir :**
  - **Option 1 (Cas général le plus fréquent) :** *« Chiffre d'affaires des autres prestations de services commerciales (BIC) »* (Taux de cotisations sociales d'environ 21,2% à 21,3%).
  - **Option 2 (Si votre CFE vous a immatriculé en profession libérale) :** *« Chiffre d'affaires des prestations de services BNC »*.
- **Montant à inscrire :** Reportez le montant calculé dans le cadre URSSAF du tableau de bord pour le mois ou le trimestre concerné. Si vous n'avez reçu aucun virement, indiquez `0`.

---

#### B. Déclaration Annuelle des Impôts sur le Revenu (Formulaire `2042-C-PRO`)
Chaque année en mai, lors de votre déclaration de revenus sur `impots.gouv.fr`, cochez la case *« Revenus des auto-entrepreneurs / micro-entrepreneurs »*.

Reportez le montant total annuel encaissé affiché sur votre tableau de bord dans **l'une des 4 cases ci-dessous** selon votre régime :

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ MODALITÉ FISCALE RETENUE                │ CASE FORMULAIRE 2042-C-PRO │ ABATTEMENT AUTO │
├─────────────────────────────────────────┼────────────────────────────┼─────────────────┤
│ Micro-BIC SANS Versement Libératoire    │         Case 5KP           │       50 %      │
│ Micro-BIC AVEC Versement Libératoire    │         Case 5TB           │ Impôt déjà payé │
│ Micro-BNC SANS Versement Libératoire    │         Case 5HQ           │       34 %      │
│ Micro-BNC AVEC Versement Libératoire    │         Case 5TE           │ Impôt déjà payé │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

**Détail des cases :**
1. **Case 5KP (Micro-BIC Classique) :**  
   Vous n'avez pas souscrit au versement libératoire. Le fisc applique automatiquement un abattement forfaitaire de 50% représentatif de vos frais. Vous n'êtes imposé au barème de l'impôt sur le revenu que sur la moitié restante (50% de vos gains).
2. **Case 5TB (Micro-BIC avec Versement Libératoire) :**  
   Vous avez payé 1,7% d'impôt libératoire au fur et à mesure à l'URSSAF. Renseigner cette case permet d'intégrer vos revenus au calcul du Revenu Fiscal de Référence (RFR) **sans que vous ne payiez d'impôt supplémentaire**.
3. **Case 5HQ (Micro-BNC Classique) :**  
   Pour les affiliés rattachés à la catégorie BNC. Abattement forfaitaire automatique de 34%.
4. **Case 5TE (Micro-BNC avec Versement Libératoire) :**  
   Pour les affiliés BNC ayant opté pour le versement libératoire de 2,2% à l'URSSAF.

---

### 3.4 TVA & Factures Amazon (Autofacturation)
- En micro-entreprise, vous bénéficiez de la franchise en base de TVA (Art. 293 B du Code Général des Impôts) jusqu'à **36 800 €** de CA annuel de prestations de services. Vos fiches et factures portent la mention légale : *« TVA non applicable, art. 293 B du CGI »*.
- Amazon Europe Core S.à r.l. étant basée au Luxembourg, les autofactures mensuelles téléchargeables sur votre Club Partenaires sont émises hors taxe avec autoliquidation de la taxe par le preneur (TVA intracommunautaire B2B).
- **Conservation :** Téléchargez chaque mois le PDF de l'autofacture Amazon et conservez-le dans un dossier d'archive avec vos relevés bancaires pendant 10 ans.

---

## Commandes Utiles et Routine Quotidienne

| Action | Commande Terminal |
| :--- | :--- |
| **Générer le site manuellement en local** | `python src/agent_engine.py` |
| **Enregistrer un encaissement Amazon** | `python src/compta_manager.py --add --date "AAAA-MM-JJ" --montant 120.00 --ref "AMZ-2026-XX"` |
| **Lister les encaissements enregistrés** | `python src/compta_manager.py --list` |
| **Actualiser le tableau de bord fiscal HTML** | `python src/compta_manager.py --report` |
| **Ouvrir le tableau de bord fiscal (Windows)**| `start compta_impots/tableau_de_bord_fiscal.html` |
| **Tester le site web localement** | `python -m http.server 8000 --directory docs` |

---
*Projet conçu pour une totale autonomie, zéro frais d'infrastructure et une conformité légale et fiscale irréprochable.*
