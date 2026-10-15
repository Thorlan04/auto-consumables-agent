"""Module Comptable & Fiscal pour Micro-Entreprises Françaises.

Conforme aux dispositions de :
- L'article L123-28 du Code de commerce (tenue obligatoire du Livre des Recettes).
- L'article 286 du Code Général des Impôts (mentions obligatoires et chronologie).
- Formulaire officiel de déclaration des revenus 2042-C-PRO (cases 5KP, 5TB, 5HQ, 5TE).
- Portail autoentrepreneur.urssaf.fr pour les télédéclarations mensuelles ou trimestrielles.

Ce script permet d'enregistrer les paiements de commissions d'affiliation Amazon Partenaires
et génère un tableau de bord fiscal hors-ligne, sécurisé et imprimable en PDF.
"""

from __future__ import annotations

import argparse
import csv
import datetime
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

BASE_DIR = Path(__file__).resolve().parent.parent
COMPTA_DIR = BASE_DIR / "compta_impots"
CSV_FILE = COMPTA_DIR / "livre_des_recettes_officiel.csv"
HTML_DASHBOARD = COMPTA_DIR / "tableau_de_bord_fiscal.html"

CSV_HEADERS = [
    "Date_Encaissement",
    "Numero_Piece_Autofacture",
    "Client",
    "Nature_Operation",
    "Montant_Brut_EUR",
    "Mode_Reglement",
]


class ReceiptEntry:
    def __init__(
        self,
        date_str: str,
        ref: str,
        client: str,
        nature: str,
        montant: float,
        mode: str,
    ):
        self.date_str = date_str
        self.ref = ref
        self.client = client
        self.nature = nature
        self.montant = round(float(montant), 2)
        self.mode = mode

        # Parsing de date pour le tri et le regroupement
        try:
            self.date_obj = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            try:
                self.date_obj = datetime.datetime.strptime(date_str, "%d/%m/%Y").date()
                self.date_str = self.date_obj.strftime("%Y-%m-%d")
            except ValueError:
                self.date_obj = datetime.date.today()

        self.year = self.date_obj.year
        self.month = self.date_obj.month
        self.quarter = (self.date_obj.month - 1) // 3 + 1


def load_receipts() -> List[ReceiptEntry]:
    """Charge l'ensemble des encaissements depuis le fichier CSV officiel."""
    COMPTA_DIR.mkdir(parents=True, exist_ok=True)
    if not CSV_FILE.exists():
        with open(CSV_FILE, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow(CSV_HEADERS)
        return []

    entries: List[ReceiptEntry] = []
    with open(CSV_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            if not row or not row.get("Date_Encaissement"):
                continue
            try:
                raw_montant = str(row.get("Montant_Brut_EUR", "0")).replace(",", ".").strip()
                montant = float(raw_montant)
            except ValueError:
                montant = 0.0

            entry = ReceiptEntry(
                date_str=row.get("Date_Encaissement", "").strip(),
                ref=row.get("Numero_Piece_Autofacture", "").strip(),
                client=row.get("Client", "").strip(),
                nature=row.get("Nature_Operation", "").strip(),
                montant=montant,
                mode=row.get("Mode_Reglement", "").strip(),
            )
            entries.append(entry)

    # Tri chronologique obligatoire (Art. L123-28 Code de commerce)
    entries.sort(key=lambda x: (x.date_obj, x.ref))
    return entries


def save_receipts(entries: List[ReceiptEntry]):
    """Sauvegarde les encaissements dans le CSV officiel avec tri chronologique."""
    entries.sort(key=lambda x: (x.date_obj, x.ref))
    with open(CSV_FILE, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(CSV_HEADERS)
        for e in entries:
            writer.writerow([
                e.date_str,
                e.ref,
                e.client,
                e.nature,
                f"{e.montant:.2f}",
                e.mode,
            ])


def add_receipt(
    date_str: str,
    montant: float,
    ref: str,
    client: str = "Amazon Europe Core S.à r.l.",
    nature: str = "Commissions d'affiliation Amazon Partenaires",
    mode: str = "Virement SEPA",
) -> ReceiptEntry:
    """Ajoute une ligne de recette certifiée au Livre des Recettes officiel."""
    entries = load_receipts()

    # Nettoyage et formatage
    clean_date = date_str.strip()
    try:
        parsed_d = datetime.datetime.strptime(clean_date, "%Y-%m-%d").date()
    except ValueError:
        try:
            parsed_d = datetime.datetime.strptime(clean_date, "%d/%m/%Y").date()
        except ValueError:
            raise ValueError(f"Format de date invalide '{date_str}'. Utilisez 'AAAA-MM-JJ' ou 'JJ/MM/AAAA'.")
    formatted_date = parsed_d.strftime("%Y-%m-%d")

    entry = ReceiptEntry(
        date_str=formatted_date,
        ref=ref.strip(),
        client=client.strip(),
        nature=nature.strip(),
        montant=montant,
        mode=mode.strip(),
    )

    entries.append(entry)
    save_receipts(entries)
    print(f"[OK] Encaissement enregistré : {entry.date_str} | {entry.ref} | {entry.montant:.2f} € de {entry.client}")

    # Régénération immédiate du tableau de bord visuel
    generate_fiscal_dashboard(entries)
    return entry


def compute_statistics(entries: List[ReceiptEntry]):
    """Calcule les agrégations mensuelles, trimestrielles et annuelles."""
    current_year = datetime.date.today().year

    years_data: Dict[int, Dict] = {}

    for e in entries:
        y = e.year
        if y not in years_data:
            years_data[y] = {
                "total_year": 0.0,
                "months": {m: 0.0 for m in range(1, 13)},
                "quarters": {1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0},
                "entries_count": 0,
            }
        years_data[y]["total_year"] += e.montant
        years_data[y]["months"][e.month] += e.montant
        years_data[y]["quarters"][e.quarter] += e.montant
        years_data[y]["entries_count"] += 1

    # S'assurer que l'année courante existe même sans encaissement
    if current_year not in years_data:
        years_data[current_year] = {
            "total_year": 0.0,
            "months": {m: 0.0 for m in range(1, 13)},
            "quarters": {1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0},
            "entries_count": 0,
        }

    return years_data


def generate_fiscal_dashboard(entries: Optional[List[ReceiptEntry]] = None):
    """Génère le fichier HTML compta_impots/tableau_de_bord_fiscal.html complet et stylisé."""
    if entries is None:
        entries = load_receipts()

    years_data = compute_statistics(entries)
    sorted_years = sorted(years_data.keys(), reverse=True)
    current_year = datetime.date.today().year
    now_str = datetime.datetime.now().strftime("%d/%m/%Y à %H:%M")

    month_names = [
        "", "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
        "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"
    ]

    html_content = f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Livre des Recettes & Tableau de Bord Fiscal Micro-Entreprise</title>
    <style>
        :root {{
            --primary: #1e3a8a;
            --primary-light: #eff6ff;
            --secondary: #0d9488;
            --accent-urssaf: #0284c7;
            --accent-impots: #b45309;
            --text-dark: #0f172a;
            --text-muted: #64748b;
            --border: #cbd5e1;
            --bg-page: #f8fafc;
            --bg-card: #ffffff;
            --success: #15803d;
            --warning-bg: #fffbeb;
            --warning-border: #fef08a;
        }}

        *, *::before, *::after {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background-color: var(--bg-page);
            color: var(--text-dark);
            line-height: 1.5;
            padding: 2rem 1rem;
        }}

        .dashboard-container {{
            max-width: 1200px;
            margin: 0 auto;
        }}

        header.fiscal-header {{
            background: #ffffff;
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 1.75rem 2rem;
            margin-bottom: 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        }}

        .header-title h1 {{
            font-size: 1.6rem;
            color: var(--primary);
            margin-bottom: 0.35rem;
        }}

        .header-title p {{
            color: var(--text-muted);
            font-size: 0.9rem;
        }}

        .header-badges {{
            display: flex;
            flex-direction: column;
            align-items: flex-end;
            gap: 0.35rem;
        }}

        .badge-official {{
            background-color: #dbeafe;
            color: #1e40af;
            font-size: 0.8rem;
            font-weight: 700;
            padding: 0.35rem 0.75rem;
            border-radius: 9999px;
            text-transform: uppercase;
        }}

        .card {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 1.5rem;
            margin-bottom: 2rem;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        }}

        .card-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 2px solid var(--border);
            padding-bottom: 0.75rem;
            margin-bottom: 1.25rem;
        }}

        .card-header h2 {{
            font-size: 1.25rem;
            color: var(--primary);
        }}

        /* Grille des déclarations fiscales */
        .tax-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
            gap: 1.25rem;
            margin-bottom: 1.5rem;
        }}

        .tax-box {{
            background: #f8fafc;
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 1.25rem;
            position: relative;
        }}

        .tax-box.impots {{
            border-left: 5px solid var(--accent-impots);
        }}

        .tax-box.urssaf {{
            border-left: 5px solid var(--accent-urssaf);
        }}

        .tax-box .case-name {{
            font-size: 0.85rem;
            font-weight: 700;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}

        .tax-box .case-code {{
            display: inline-block;
            background: #1e293b;
            color: #ffffff;
            font-weight: 800;
            font-size: 1rem;
            padding: 0.15rem 0.5rem;
            border-radius: 4px;
            margin: 0.35rem 0;
        }}

        .tax-box .amount {{
            font-size: 1.75rem;
            font-weight: 800;
            color: var(--primary);
            margin: 0.25rem 0;
        }}

        .tax-box .description {{
            font-size: 0.8rem;
            color: #475569;
            line-height: 1.4;
        }}

        /* Tableaux */
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.9rem;
            margin-top: 0.5rem;
        }}

        th {{
            background-color: #f1f5f9;
            color: #334155;
            text-align: left;
            padding: 0.75rem 1rem;
            font-weight: 600;
            border-bottom: 2px solid var(--border);
        }}

        td {{
            padding: 0.75rem 1rem;
            border-bottom: 1px solid var(--border);
        }}

        tr:nth-child(even) td {{
            background-color: #f8fafc;
        }}

        .text-right {{
            text-align: right;
        }}

        .text-center {{
            text-align: center;
        }}

        .amount-bold {{
            font-weight: 700;
            color: var(--primary);
        }}

        .notice-legal {{
            background-color: var(--warning-bg);
            border: 1px solid var(--warning-border);
            border-left: 4px solid #f59e0b;
            padding: 1rem 1.25rem;
            border-radius: 6px;
            font-size: 0.85rem;
            color: #78350f;
            margin-bottom: 1.5rem;
        }}

        .btn-print {{
            background-color: var(--primary);
            color: #ffffff;
            border: none;
            padding: 0.6rem 1.25rem;
            font-size: 0.9rem;
            font-weight: 600;
            border-radius: 6px;
            cursor: pointer;
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
        }}

        .btn-print:hover {{
            background-color: #1e40af;
        }}

        /* Impression propre pour contrôle fiscal / URSSAF */
        @media print {{
            body {{
                background-color: #ffffff;
                padding: 0;
                font-size: 11pt;
            }}
            .btn-print, .no-print {{
                display: none !important;
            }}
            .card {{
                box-shadow: none;
                border: 1px solid #94a3b8;
                page-break-inside: avoid;
            }}
            header.fiscal-header {{
                border-bottom: 2px solid #000;
            }}
        }}
    </style>
</head>
<body>
    <div class="dashboard-container">
        <!-- En-tête officiel -->
        <header class="fiscal-header">
            <div class="header-title">
                <h1>Tableau de Bord Fiscal & Social Micro-Entreprise</h1>
                <p>Suivi officiel du Chiffre d'Affaires • Déclarations URSSAF & Formulaire 2042-C-PRO</p>
                <p style="font-size: 0.8rem; color: #64748b; margin-top: 0.25rem;">
                    Généré hors-ligne le <strong>{now_str}</strong> • Strictement confidentiel (usage interne)
                </p>
            </div>
            <div class="header-badges">
                <span class="badge-official">Conforme Art. L123-28 Code de Commerce</span>
                <button class="btn-print no-print" onclick="window.print()">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 6 2 18 2 18 9"></polyline><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"></path><rect x="6" y="14" width="12" height="8"></rect></svg>
                    Imprimer / Exporter en PDF
                </button>
            </div>
        </header>

        <!-- Avertissement Légal Pédagogique -->
        <div class="notice-legal">
            <strong>Rappel Réglementaire Micro-Entreprise :</strong>
            En micro-entreprise (auto-entrepreneur), la comptabilité repose sur une <strong>comptabilité d'encaissement</strong>. Seuls les montants bruts réellement encaissés (virement reçu sur votre compte bancaire) au cours du mois ou du trimestre doivent être déclarés. Les commissions Amazon sont versées par <em>Amazon Europe Core S.à r.l.</em> (Luxembourg) sous forme d'autofacture mensuelle.
        </div>
"""

    # Section pour chaque année fiscale (en commençant par la plus récente)
    for year in sorted_years:
        ydata = years_data[year]
        total_year = ydata["total_year"]
        quarters = ydata["quarters"]
        months = ydata["months"]

        html_content += f"""
        <!-- ==================== ANNÉE FISCALE {year} ==================== -->
        <section class="card">
            <div class="card-header">
                <h2>Exercice Fiscal Civil : Année {year}</h2>
                <div style="font-size: 1.1rem; font-weight: 700; color: var(--primary);">
                    Chiffre d'Affaires Annuel Encaissé : <span style="font-size: 1.4rem;">{total_year:,.2f} €</span>
                </div>
            </div>

            <!-- Déclaration Annuelle des Revenus (Impôts.gouv - Formulaire 2042-C-PRO) -->
            <h3 style="font-size: 1.05rem; color: var(--accent-impots); margin-bottom: 0.75rem;">
                1. Déclaration Annuelle aux Impôts (Formulaire 2042-C-PRO au printemps {year + 1})
            </h3>
            <p style="font-size: 0.85rem; color: var(--text-muted); margin-bottom: 1rem;">
                Reportez le montant total de <strong>{total_year:,.2f} €</strong> dans <u>une seule</u> des cases ci-dessous selon votre option fiscale :
            </p>

            <div class="tax-grid">
                <div class="tax-box impots">
                    <div class="case-name">Micro-BIC Classique (Sans VFL)</div>
                    <div class="case-code">Case 5KP</div>
                    <div class="amount">{total_year:,.2f} €</div>
                    <div class="description">
                        Prestations de services commerciales. L'administration fiscale applique automatiquement un <strong>abattement forfaitaire de 50%</strong>. Le solde est soumis au barème progressif de l'impôt sur le revenu.
                    </div>
                </div>

                <div class="tax-box impots">
                    <div class="case-name">Micro-BIC avec Versement Libératoire</div>
                    <div class="case-code">Case 5TB</div>
                    <div class="amount">{total_year:,.2f} €</div>
                    <div class="description">
                        Si vous avez opté pour le Versement Fiscal Libératoire (1,7% payé avec vos cotisations URSSAF). Ce montant sert uniquement au calcul de votre revenu fiscal de référence (RFR) sans double imposition.
                    </div>
                </div>

                <div class="tax-box impots">
                    <div class="case-name">Micro-BNC Classique (Sans VFL)</div>
                    <div class="case-code">Case 5HQ</div>
                    <div class="amount">{total_year:,.2f} €</div>
                    <div class="description">
                        Si votre activité d'affiliation a été enregistrée en libéral / prestations intellectuelles. L'administration applique un <strong>abattement forfaitaire de 34%</strong>.
                    </div>
                </div>

                <div class="tax-box impots">
                    <div class="case-name">Micro-BNC avec Versement Libératoire</div>
                    <div class="case-code">Case 5TE</div>
                    <div class="amount">{total_year:,.2f} €</div>
                    <div class="description">
                        Si vous avez opté pour le versement libératoire en statut BNC (2,2% payé à l'URSSAF). Déclaration pour calcul du taux effectif et du RFR.
                    </div>
                </div>
            </div>

            <!-- Déclaration Périodique URSSAF -->
            <h3 style="font-size: 1.05rem; color: var(--accent-urssaf); margin: 1.5rem 0 0.75rem;">
                2. Déclarations Périodiques URSSAF ({year}) sur <code>autoentrepreneur.urssaf.fr</code>
            </h3>
            <p style="font-size: 0.85rem; color: var(--text-muted); margin-bottom: 0.75rem;">
                Ligne à compléter sur le portail URSSAF : <em>« Chiffre d'affaires des autres prestations de services »</em> (BIC ou BNC selon votre notification d'affiliation).
            </p>

            <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; margin-bottom: 1.5rem;">
                <div class="tax-box urssaf">
                    <div class="case-name">1er Trimestre (Jan - Mar)</div>
                    <div class="amount" style="font-size: 1.35rem;">{quarters[1]:,.2f} €</div>
                    <div class="description">À télédéclarer avant le 30 Avril {year}</div>
                </div>
                <div class="tax-box urssaf">
                    <div class="case-name">2ème Trimestre (Avr - Jun)</div>
                    <div class="amount" style="font-size: 1.35rem;">{quarters[2]:,.2f} €</div>
                    <div class="description">À télédéclarer avant le 31 Juillet {year}</div>
                </div>
                <div class="tax-box urssaf">
                    <div class="case-name">3ème Trimestre (Juil - Sep)</div>
                    <div class="amount" style="font-size: 1.35rem;">{quarters[3]:,.2f} €</div>
                    <div class="description">À télédéclarer avant le 31 Octobre {year}</div>
                </div>
                <div class="tax-box urssaf">
                    <div class="case-name">4ème Trimestre (Oct - Déc)</div>
                    <div class="amount" style="font-size: 1.35rem;">{quarters[4]:,.2f} €</div>
                    <div class="description">À télédéclarer avant le 31 Janvier {year + 1}</div>
                </div>
            </div>

            <!-- Détail Mensuel -->
            <h4 style="font-size: 0.95rem; color: var(--text-dark); margin-bottom: 0.5rem;">
                Ventilation Mensuelle (Si vous avez opté pour la déclaration mensuelle URSSAF) :
            </h4>
            <table>
                <thead>
                    <tr>
                        <th>Mois</th>
                        <th class="text-right">Montant Encaissé (€)</th>
                        <th>Échéance Limite Déclaration URSSAF</th>
                        <th>Statut</th>
                    </tr>
                </thead>
                <tbody>
        """

        for m in range(1, 13):
            m_amount = months[m]
            deadline_month = m + 1 if m < 12 else 1
            deadline_year = year if m < 12 else year + 1
            deadline_str = f"Dernier jour de {month_names[deadline_month]} {deadline_year}"

            html_content += f"""
                    <tr>
                        <td><strong>{month_names[m]} {year}</strong></td>
                        <td class="text-right amount-bold">{m_amount:,.2f} €</td>
                        <td>{deadline_str}</td>
                        <td><span style="font-size: 0.8rem; color: {'#15803d' if m_amount > 0 else '#94a3b8'};">{'Recette enregistrée' if m_amount > 0 else 'Néant (0 €)'}</span></td>
                    </tr>
            """

        html_content += """
                </tbody>
            </table>
        </section>
        """

    # Section 3 : Livre des Recettes Officiel Exhaustif
    html_content += f"""
        <!-- ==================== LIVRE DES RECETTES OFFICIEL ==================== -->
        <section class="card">
            <div class="card-header">
                <h2>Livre des Recettes Chronologique (Article L123-28 du Code de commerce)</h2>
                <div style="font-size: 0.9rem; color: var(--text-muted);">
                    Total Opérations : <strong>{len(entries)}</strong>
                </div>
            </div>

            <p style="font-size: 0.85rem; color: var(--text-muted); margin-bottom: 1rem;">
                Ce registre doit être conservé pendant une durée minimale de 10 ans (article L123-22 du Code de commerce) avec les pièces justificatives associées (relevés de compte bancaire et autofactures mensuelles éditées par Amazon).
            </p>

            <table>
                <thead>
                    <tr>
                        <th>Date d'Encaissement</th>
                        <th>N° Pièce / Réf. Autofacture</th>
                        <th>Client / Tiers</th>
                        <th>Nature de l'Opération</th>
                        <th>Mode de Paiement</th>
                        <th class="text-right">Montant Brut (€)</th>
                    </tr>
                </thead>
                <tbody>
    """

    if not entries:
        html_content += """
                    <tr>
                        <td colspan="6" class="text-center" style="padding: 2rem; color: #94a3b8;">
                            Aucune recette enregistrée pour le moment.<br>
                            Utilisez la commande : <code>python src/compta_manager.py --add --date "2026-10-28" --montant 145.50 --ref "AMZ-2026-10"</code>
                        </td>
                    </tr>
        """
    else:
        running_total = 0.0
        for e in entries:
            running_total += e.montant
            html_content += f"""
                    <tr>
                        <td><strong>{e.date_str}</strong></td>
                        <td><code>{e.ref}</code></td>
                        <td>{e.client}</td>
                        <td>{e.nature}</td>
                        <td>{e.mode}</td>
                        <td class="text-right amount-bold">{e.montant:,.2f} €</td>
                    </tr>
            """

        html_content += f"""
                    <tr style="background-color: #f1f5f9; font-weight: 800; border-top: 2px solid var(--border);">
                        <td colspan="5" style="text-align: right; text-transform: uppercase;">Total Cumulé Historique :</td>
                        <td class="text-right amount-bold" style="font-size: 1.15rem; color: var(--primary);">{running_total:,.2f} €</td>
                    </tr>
        """

    html_content += f"""
                </tbody>
            </table>
        </section>

        <!-- Conseils Pratiques Gestion TVA et Franchise -->
        <section class="card" style="background: #f8fafc;">
            <h3 style="font-size: 1.05rem; color: var(--text-dark); margin-bottom: 0.75rem;">
                Repères Légaux : Plafonds & TVA (Art. 293 B du CGI)
            </h3>
            <ul style="margin-left: 1.5rem; font-size: 0.85rem; color: #475569; line-height: 1.7;">
                <li><strong>Franchise en base de TVA (Prestations de services) :</strong> Seuil de base de 36 800 € et seuil majoré de 39 100 €. En dessous, vous ne facturez pas de TVA ("TVA non applicable, art. 293 B du CGI").</li>
                <li><strong>Seuil de Chiffre d'Affaires Micro-Entreprise :</strong> Plafond de 77 700 € annuel pour les prestations de services en régime micro-social.</li>
                <li><strong>Territorialité des commissions Amazon :</strong> Amazon Europe Core S.à r.l. étant basée au Luxembourg, les autofactures sont émises hors taxe avec autoliquidation de TVA intracommunautaire (à reporter éventuellement sur la déclaration européenne de services DES si applicable).</li>
            </ul>
        </section>

        <footer style="text-align: center; font-size: 0.8rem; color: #94a3b8; margin-top: 2rem;">
            Document généré automatiquement par <code>auto-consumables-agent</code> • Registre interne non public
        </footer>
    </div>
</body>
</html>
"""

    with open(HTML_DASHBOARD, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"[OK] Tableau de bord fiscal mis à jour : {HTML_DASHBOARD}")


def list_receipts():
    """Affiche la liste des encaissements dans le terminal."""
    entries = load_receipts()
    print("=" * 80)
    print(f"LIVRE DES RECETTES OFFICIEL MICRO-ENTREPRISE ({len(entries)} opérations)")
    print("=" * 80)
    if not entries:
        print("Aucune recette enregistrée.")
        return

    print(f"{'Date':<12} | {'Réf / N° Pièce':<18} | {'Client':<26} | {'Montant (€)':>12}")
    print("-" * 80)
    total = 0.0
    for e in entries:
        total += e.montant
        print(f"{e.date_str:<12} | {e.ref:<18} | {e.client[:25]:<26} | {e.montant:>10.2f} €")
    print("-" * 80)
    print(f"{'TOTAL CUMULÉ':<58} | {total:>10.2f} €")
    print("=" * 80)


def main():
    parser = argparse.ArgumentParser(
        description="Gestionnaire du Livre des Recettes et Tableau de Bord Fiscal Micro-Entreprise"
    )
    parser.add_argument("--add", action="store_true", help="Ajouter un encaissement officiel")
    parser.add_argument("--date", type=str, help="Date de l'encaissement (AAAA-MM-JJ ou JJ/MM/AAAA)")
    parser.add_argument("--montant", type=float, help="Montant brut perçu en euros")
    parser.add_argument("--ref", type=str, help="Numéro d'autofacture Amazon ou référence virement (ex: AMZ-2026-10)")
    parser.add_argument("--client", type=str, default="Amazon Europe Core S.à r.l.", help="Nom du tiers payeur")
    parser.add_argument("--nature", type=str, default="Commissions d'affiliation Amazon Partenaires", help="Nature de l'opération")
    parser.add_argument("--mode", type=str, default="Virement SEPA", help="Mode de règlement")
    parser.add_argument("--list", action="store_true", help="Lister les recettes enregistrées")
    parser.add_argument("--report", action="store_true", help="Générer ou rafraîchir le tableau de bord fiscal HTML")

    args = parser.parse_args()

    if args.add:
        if not args.date or args.montant is None or not args.ref:
            print("[ERREUR] Pour ajouter une recette, spécifiez --date, --montant et --ref.")
            print("Exemple : python src/compta_manager.py --add --date '2026-10-28' --montant 145.50 --ref 'AMZ-2026-10'")
            sys.exit(1)
        add_receipt(
            date_str=args.date,
            montant=args.montant,
            ref=args.ref,
            client=args.client,
            nature=args.nature,
            mode=args.mode,
        )
    elif args.list:
        list_receipts()
    elif args.report:
        generate_fiscal_dashboard()
    else:
        # Action par défaut : rafraîchit le rapport et affiche le résumé
        list_receipts()
        generate_fiscal_dashboard()


if __name__ == "__main__":
    main()
