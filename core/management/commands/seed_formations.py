"""
core/management/commands/seed_formations.py

Seed command for SARL MOUASSASSET TAMAYOUZ LILIDARA W ESSALAMA
Loads:
  • Institute & business-line settings (InstituteInfo, FormationInfo, BureauEtudeInfo)
  • Formes juridiques  (SARL, EURL, SPA, SNC, GIE, Autre)
  • Formation categories & catalog  (5 categories, 46 formations)
  • 12 clients (ENTREPRISE) extracted from the 2026 invoice set
  • 14 finalized FORMATION invoices (phase=FINALE, status=UNPAID)
  • Admin user (admin / admin1234!)

Usage:
    python manage.py seed_formations
    python manage.py seed_formations --clear    # wipe before re-seeding
"""

import datetime
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from clients.models import Client, FormeJuridique
from core.models import BureauEtudeInfo, FormationInfo, InstituteInfo
from financial.models import Invoice, InvoiceItem, InvoiceSequence
from formations.models import Formation, FormationCategory


TVA_9 = Decimal("0.09")
TVA_19 = Decimal("0.19")
ZERO = Decimal("0.00")


class Command(BaseCommand):
    help = (
        "Seed institute settings, formation catalog, clients, invoices, and admin user."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete existing invoices, clients, and formations before seeding.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options["clear"]:
            self._clear_data()

        self._seed_formes_juridiques()
        self._seed_institute()
        self._seed_formation_catalog()
        clients = self._seed_clients()
        self._seed_invoices(clients)
        self._update_sequences()
        self._seed_admin_user()

        self.stdout.write(self.style.SUCCESS("\n✓ Seed terminé avec succès.\n"))

    # ------------------------------------------------------------------ #
    # Clear
    # ------------------------------------------------------------------ #
    def _clear_data(self):
        InvoiceItem.objects.all().delete()
        Invoice.objects.all().delete()
        InvoiceSequence.objects.all().delete()
        Client.objects.all().delete()
        Formation.objects.all().delete()
        FormationCategory.objects.all().delete()
        self.stdout.write("  ✓ Données existantes supprimées")

    # ------------------------------------------------------------------ #
    # Formes juridiques
    # ------------------------------------------------------------------ #
    def _seed_formes_juridiques(self):
        entries = [
            ("SARL", "Société à Responsabilité Limitée"),
            ("EURL", "Entreprise Unipersonnelle à Responsabilité Limitée"),
            ("SPA", "Société Par Actions"),
            ("SNC", "Société en Nom Collectif"),
            ("GIE", "Groupement d'Intérêt Économique"),
            ("Autre", "Forme juridique non listée ou non applicable"),
        ]
        for name, desc in entries:
            FormeJuridique.objects.get_or_create(
                name=name, defaults={"description": desc}
            )
        self.stdout.write(f"  ✓ {len(entries)} formes juridiques")

    # ------------------------------------------------------------------ #
    # Institute / business-line singleton settings
    # ------------------------------------------------------------------ #
    def _seed_institute(self):
        # Common fields for all three models (only those that exist)
        common = {
            "address": "CITE LOTIS HACHEMI 1ere TRANCHE ETAGE 1 ET 2",
            "phone": "036527557",
            "rc": "21B0094443-00/19",
            "nif": "002119009444326",
            "nis": "002119010021763",
            "article_imposition": "19011780071",
            "bank_name": "BNA",
            "bank_rib": "001-00711030000 1829-41",
            "bank_account": "",
        }

        # InstituteInfo (has city, postal_code, email, agrement_number)
        InstituteInfo.objects.update_or_create(
            pk=1,
            defaults={
                "name": "SARL MOUASSASSET TAMAYOUZ LILIDARA W ESSALAMA",
                "abbreviation": "MTL ESSALAMA",
                "email": "",
                "agrement_number": "EFP 003-14/03/2022",
                "city": "SETIF",
                "postal_code": "19000",
                **common,
            },
        )

        # FormationInfo
        FormationInfo.objects.update_or_create(
            pk=1,
            defaults={
                "name": "Centre de Formation Tamayouz",
                "invoice_prefix": "F",
                "proforma_prefix": "FP",
                "tva_applicable": True,
                "tva_rate": TVA_9,
                "agrement_number": "EFP 003-14/03/2022",
                **common,
            },
        )

        # BureauEtudeInfo
        BureauEtudeInfo.objects.update_or_create(
            pk=1,
            defaults={
                "name": "Bureau d'Étude Tamayouz",
                "invoice_prefix": "E",
                "proforma_prefix": "FP-E",
                "tva_applicable": True,
                "tva_rate": TVA_19,
                **common,
            },
        )

        self.stdout.write("  ✓ InstituteInfo / FormationInfo / BureauEtudeInfo")

    # ------------------------------------------------------------------ #
    # Formation categories and catalog
    # ------------------------------------------------------------------ #
    def _seed_formation_catalog(self):
        from django.utils.text import slugify

        # (code, name, color, [(title, duration_days, duration_hours), ...])
        catalog = [
            (
                "RH",
                "Management des Ressources Humaines",
                "#6366F1",
                [
                    (
                        "Enjeux de la Fonction RH et le Management des Ressources Humaines",
                        2,
                        16,
                    ),
                    ("Gestion des Emplois et des Compétences (GPEC)", 3, 24),
                    ("Techniques de Résolution des Conflits", 2, 16),
                    (
                        "Emprise du Droit de Travail National sur les Pratiques GRH",
                        2,
                        16,
                    ),
                    ("Législation et Sécurité Sociale", 2, 16),
                    ("Analyse et Évolution des Systèmes de Rémunération", 2, 16),
                    ("Système d'Information RH et Tableau de Bord", 2, 16),
                    ("Les Indicateurs de Performance KPI", 1, 8),
                    ("Politique de Rémunération", 1, 8),
                    ("Formation ISO 9001 / ISO 14001 / ISO 45001", 3, 24),
                    ("Élaboration des Budgets pour RH", 1, 8),
                ],
            ),
            (
                "COM",
                "Communication et Leadership",
                "#F59E0B",
                [
                    ("Gestion de Conflits", 2, 16),
                    ("Maîtrise du Temps et Gestion des Priorités", 2, 16),
                    ("Communication Interpersonnelle et leurs Techniques", 2, 16),
                    ("Gestion d'Équipe", 2, 16),
                    ("Agent Commercial", 3, 24),
                    ("Les Écrits Professionnels et Administratifs", 2, 16),
                    ("Animation de Réunions et Prise de Parole en Public", 2, 16),
                ],
            ),
            (
                "PMD",
                "Gestion de la Maintenance",
                "#10B981",
                [
                    ("Gestion de la Maintenance Assistée par Ordinateur (GMAO)", 3, 24),
                    ("Maintenance Basée sur la Fiabilité (MBF)", 3, 24),
                    (
                        "Extraire les Bonnes Informations des Tableaux de Bord — Analyse",
                        2,
                        16,
                    ),
                    ("Maîtrise de la Totale Productive Maintenance (TPM)", 3, 24),
                    ("Formation Method Maintenance", 2, 16),
                ],
            ),
            (
                "HSE",
                "Formation HSE",
                "#EF4444",
                [
                    ("IOSH Managing Safely", 4, 32),
                    ("Superviseur HSE", 5, 40),
                    ("Protections Électriques — Réseaux et Centrales", 3, 24),
                    ("Leadership et Culture HSE", 2, 16),
                    ("Veille Réglementaire HSE — Lois, Règles, Normes", 2, 16),
                    ("Sécurité Basée sur le Comportement (BBS)", 2, 16),
                    ("Techniques d'Investigation des Accidents et Incidents", 3, 24),
                    ("Commission Paritaire d'Hygiène et de Sécurité (CPHS)", 2, 16),
                    ("Habilitation Conduite des Chariots Élévateurs", 1, 8),
                    ("HACCP — Hazard Analysis Critical Control Point", 3, 24),
                    ("Habilitation Électrique", 3, 24),
                    ("Habilitation d'Utilisation Produit Chimique", 4, 32),
                    ("Premier Secours", 1, 8),
                    ("Lutte Contre l'Incendie", 1, 8),
                    ("Habilitation Travail en Hauteur", 2, 16),
                    ("Conduite en Sécurité des Engins", 2, 16),
                    ("Risque Hydrogène Sulfuré H2S", 1, 8),
                    ("Atmosphère Explosive Niveau 01 — ISM-ATEX 1E", 3, 24),
                    ("Atmosphère Explosive Niveau 02 — ISM-ATEX 2EM", 3, 24),
                    ("Conduite Sécuritaire des Ponts Roulants", 2, 16),
                    ("Délégué Environnement", 2, 16),
                    ("Sensibilisation Risque à l'Activité de Carrières", 2, 16),
                    ("Audit SMQ", 3, 24),
                ],
            ),
            (
                "INFO",
                "Informatique",
                "#3B82F6",
                [
                    ("Excel et Word Avancés", 2, 16),
                    ("Power BI", 2, 16),
                ],
            ),
        ]

        total = 0
        for code, cat_name, color, formations in catalog:
            cat, _ = FormationCategory.objects.get_or_create(
                code=code,
                defaults={"name": cat_name, "color": color},
            )
            for title, days, hours in formations:
                Formation.objects.get_or_create(
                    slug=slugify(title)[:255],
                    defaults={
                        "category": cat,
                        "title": title,
                        "duration_days": days,
                        "duration_hours": hours,
                        "base_price": ZERO,
                        "is_active": True,
                    },
                )
                total += 1

        self.stdout.write(f"  ✓ 5 catégories, {total} formations")

    # ------------------------------------------------------------------ #
    # Clients (aligned with initial_db.json)
    # ------------------------------------------------------------------ #
    def _seed_clients(self):
        fj = {
            n: FormeJuridique.objects.get(name=n)
            for n in ("SARL", "EURL", "SPA", "SNC")
        }
        E = Client.ClientType.ENTREPRISE

        # (internal_key, field_dict)
        specs = [
            (
                "metal_steel",
                dict(
                    name="SARL Metal Steel Company .LTD Setif",
                    client_type=E,
                    forme_juridique=fj["SARL"],
                    address="Cité Houari Boumediene Rue Ounis Hamlaoui",
                    city="Sétif",
                    activity_sector="Fabrication métal (fonderie)",
                    rc="15B0091747-00/19",
                    nif="001519009174778",
                    nis="001519200026459",
                    article_imposition="19206116073",
                ),
            ),
            (
                "gs_automation",
                dict(
                    name="EURL G S AUTOMATION",
                    client_type=E,
                    forme_juridique=fj["EURL"],
                    address="43 Rue El Joundi Boukhaloua Cheikh, Local N°04, Es Seddikia",
                    city="Oran",
                    activity_sector="Engineering & Services",
                    rc="16B0116457-00/31",
                    nif="001631011645745",
                    nis="001631030034561",  # fixed
                    article_imposition="316464471038",
                ),
            ),
            (
                "acg_sim",
                dict(
                    name="SPA ACG SIM",
                    client_type=E,
                    forme_juridique=fj["SPA"],
                    address="EL HAMOUL CLASSE 13 GP 69 ET 67 EL KARMA",
                    city="Oran",
                    activity_sector="Transformation Des Produits Alimentaires",
                    rc="16B0809244-00/31",
                    nif="001609080924405",
                    nis="001609010028853",
                ),
            ),
            (
                "smofe",
                dict(
                    name="SARL SMOFE",
                    client_type=E,
                    forme_juridique=fj["SARL"],
                    address="CITE TELIDJENE",
                    city="Sétif",
                    activity_sector="Importation des Équipements et Matériels pour la Fabrication",
                    rc="03B0085034-19/00",
                    nif="000319008503407",
                    nis="000319010143268",
                    article_imposition="19013149011",
                ),
            ),
            (
                "kebiche",
                dict(
                    name="SNC KEBICHE ABDELHALIM ET CIE",
                    client_type=E,
                    forme_juridique=fj["SNC"],
                    address="ELKEF LAHMAR",
                    city="Sétif",
                    activity_sector="Fabrication Métallique — galvanisation à chaud",
                    rc="04B0085710-00/19",
                    nif="000419008571081",
                    nis="000419340810946",
                    article_imposition="19343224044",
                ),
            ),
            (
                "riadh_el_feth",
                dict(
                    name="SARL GROUPE RIADH EL-FETH",
                    client_type=E,
                    forme_juridique=fj["SARL"],
                    address="BD Beggag Bouzid Cité Financiere",
                    city="Sétif",
                    activity_sector="Fabrication De Cables Electriques Et Telephoniques",
                    rc="97B0082016-00/19",
                    nif="09971900820164600000",  # fixed (removed extra zero)
                    nis="099719010778514",
                ),
            ),
            (
                "tahweel_dz",
                dict(
                    name="EURL TAHWEEL DZ",
                    client_type=E,
                    forme_juridique=fj["EURL"],
                    address="Zone Act Art 5 Eme Tranche Ilot 18 Sec 309",
                    city="Sétif",
                    activity_sector="Fabrication Industrielle d'Articles De Sport et Campement",
                    rc="22B0095050-00/19",
                    nif="002219009505042",
                    nis="002219010072849",
                    article_imposition="19018404021",
                ),
            ),
            (
                "weg_algeria",
                dict(
                    name="WEG ALGERIA MOTOROS SPA",
                    client_type=E,
                    forme_juridique=fj["SPA"],
                    address="Zone industrielle LEHLATMA01/03, commune De Guidjel",
                    city="Sétif",
                    activity_sector="Production de moteurs électriques pour les appareils electromagnets",
                    rc="22B0095067-00/19",
                    nif="002219009506760",
                    article_imposition="19018690021",
                ),
            ),
            (
                "ronix",
                dict(
                    name="SARL RONIX",
                    client_type=E,
                    forme_juridique=fj["SARL"],
                    address="FID SMARA SEC 06 GRP N12 N 01 BAZER SAKRA",
                    city="Sétif",
                    activity_sector="Fabrication d'Emballages en Toutes Matières",
                    rc="18B0093479-00/19",
                    nif="001819200047451",  # fixed
                    nis="001819200047451",
                    article_imposition="19018404021",
                ),
            ),
            (
                "a2m_electronics",
                dict(
                    name="SARL A2M ELECTRONICS",
                    client_type=E,
                    forme_juridique=fj["SARL"],
                    address="Z.I N°23 a lot n°32 bis",
                    city="Sétif",
                    activity_sector="Industrie électroménager",
                    rc="10B0088547-00/19",
                    nif="001019008854771",
                    nis="001019010000771",
                ),
            ),
            (
                "bait_el_outour",
                dict(
                    name="EURL BAIT EL OUTOUR EL ALAMIA",
                    client_type=E,
                    forme_juridique=fj["EURL"],
                    address="Cité Kaaboub Coop Belle Vue Section 07 Groupe 911 Rdc",
                    city="Sétif",
                    activity_sector="Fabrication Des Produits Cosmétiques et d'hygiène Corporelle",
                    rc="22B0095116-00/19",  # fixed
                    nif="002219009511634",  # fixed
                    nis="002219010134018",  # fixed
                    article_imposition="19018604901",  # fixed
                ),
            ),
            (
                "afnes_project",
                dict(
                    name="EURL AFNES-PROJECT",
                    client_type=E,
                    forme_juridique=fj["EURL"],
                    address="CITE RYM SIDI ACHOUR COOP IMMOB IHCENE BT°01",
                    city="Annaba",
                    activity_sector="Installation et Maintenance Industrielle",
                    rc="06B0364337-00/23",
                    nif="000623036433719",
                    nis="000623010300376",
                    article_imposition="23019505645",
                ),
            ),
        ]

        clients = {}
        for key, defaults in specs:
            client, _ = Client.objects.get_or_create(
                name=defaults["name"], defaults=defaults
            )
            clients[key] = client

        self.stdout.write(f"  ✓ {len(clients)} clients")
        return clients

    # ------------------------------------------------------------------ #
    # Invoices (BC numbers from initial_db.json)
    # ------------------------------------------------------------------ #
    def _seed_invoices(self, C: dict):
        """
        C = dict of client_key → Client instance.

        Strategy to preserve exact invoice amounts without fighting model
        validation logic:
          1. Create Invoice in PROFORMA / DRAFT state.
          2. Bulk-create InvoiceItems (bypasses is_locked check and
             recalculate_amounts; total_ht is computed explicitly).
          3. Bulk-update Invoice to FINALE / UNPAID with all snapshot fields
             and the exact amounts as they appear on the printed invoices.
        """
        PP = InvoiceItem.PricingMode.PER_PERSON
        PD = InvoiceItem.PricingMode.PER_DAY
        FF = InvoiceItem.PricingMode.FORFAIT
        D = Decimal

        # Invoice specifications (BC numbers updated from JSON)
        specs = [
            # ── 001 / Metal Steel — Superviseur HSE ──────────────────
            dict(
                reference="001/2026",
                date=datetime.date(2026, 2, 8),
                client=C["metal_steel"],
                bc="03/2026",  # updated
                bc_date=None,
                mode="",
                amount_ht=D("100000.00"),
                amount_tva=D("9000.00"),
                amount_ttc=D("109000.00"),
                items=[
                    (1, "Formation Superviseur HSE", PP, D("2"), D("5"), D("50000.00")),
                ],
            ),
            # ── 002 / GS Automation — ISM-ATEX 2EM (forfait) ─────────
            dict(
                reference="0022026",
                date=datetime.date(2026, 2, 10),
                client=C["gs_automation"],
                bc="001-2026",  # updated
                bc_date=None,
                mode="",
                amount_ht=D("192660.56"),
                amount_tva=D("17339.45"),
                amount_ttc=D("201000.01"),
                items=[
                    (
                        1,
                        "Formation certification internationale ISM-ATEX 2EM",
                        FF,
                        D("1"),
                        D("1"),
                        D("192660.56"),
                    ),
                ],
            ),
            # ── 003 / ACG SIM — ISM-ATEX 2EM × 5 ────────────────────
            dict(
                reference="0032026",
                date=datetime.date(2026, 2, 10),
                client=C["acg_sim"],
                bc="002-2026",  # updated
                bc_date=None,
                mode="",
                amount_ht=D("900000.00"),
                amount_tva=D("81000.00"),
                amount_ttc=D("981000.00"),
                items=[
                    (
                        1,
                        "Formation certification internationale ISM-ATEX 2EM",
                        PP,
                        D("5"),
                        D("1"),
                        D("180000.00"),
                    ),
                ],
            ),
            # ── 004 / SMOFE — Produit chimique 4J ────────────────────
            dict(
                reference="0042026",
                date=datetime.date(2026, 2, 10),
                client=C["smofe"],
                bc="01/2026",  # updated
                bc_date=None,
                mode="",
                amount_ht=D("220000.00"),
                amount_tva=D("19800.00"),
                amount_ttc=D("239800.00"),
                items=[
                    (
                        1,
                        "Formation habilitation d'utilisation Produit chimique (12 Personnes)",
                        PD,
                        D("1"),
                        D("4"),
                        D("55000.00"),
                    ),
                ],
            ),
            # ── 005 / Kebiche — Carrières + HSE ──────────────────────
            dict(
                reference="005/2026",
                date=datetime.date(2026, 2, 12),
                client=C["kebiche"],
                bc="001/2026",  # updated
                bc_date=None,
                mode=Invoice.PaymentMode.CHEQUE,
                amount_ht=D("138000.00"),
                amount_tva=D("12420.00"),
                amount_ttc=D("150420.00"),
                items=[
                    (
                        1,
                        "Formation sensibilisation risqué à l'activité de carrières",
                        PD,
                        D("1"),
                        D("2"),
                        D("45000.00"),
                    ),
                    (2, "Formation Superviseur HSE", PP, D("1"), D("1"), D("48000.00")),
                ],
            ),
            # ── 006 / Riadh El-Feth — Chariots élévateurs (20p) ──────
            dict(
                reference="0062026",
                date=datetime.date(2026, 2, 12),
                client=C["riadh_el_feth"],
                bc="02/2026",  # updated
                bc_date=None,
                mode="",
                amount_ht=D("440000.00"),
                amount_tva=D("18000.00"),
                amount_ttc=D("458000.00"),
                items=[
                    (
                        1,
                        "Formation L'Habilitation Conduit de Chariots Élévateur",
                        PP,
                        D("20"),
                        D("1"),
                        D("22000.00"),
                    ),
                    (2, "Frais Pédagogique", PP, D("18"), D("1"), D("1000.00")),
                ],
            ),
            # ── 007 / Tahweel DZ — Communication 3J ──────────────────
            dict(
                reference="0072026",
                date=datetime.date(2026, 2, 25),
                client=C["tahweel_dz"],
                bc="001-2026",  # updated
                bc_date=None,
                mode="",
                amount_ht=D("195000.00"),
                amount_tva=D("17550.00"),
                amount_ttc=D("212550.00"),
                items=[
                    (1, "Formation Communication", PD, D("1"), D("3"), D("65000.00")),
                ],
            ),
            # ── 008 / WEG Algeria — Audit SMQ 3J ──────────────────────
            dict(
                reference="0082026",
                date=datetime.date(2026, 2, 25),
                client=C["weg_algeria"],
                bc="10-2026",  # updated
                bc_date=None,
                mode="",
                amount_ht=D("204000.00"),
                amount_tva=D("18360.00"),
                amount_ttc=D("222360.00"),
                items=[
                    (1, "Formation Audit SMQ", PD, D("1"), D("3"), D("68000.00")),
                ],
            ),
            # ── 009 / Ronix — IOSH MS 1P ──────────────────────────────
            dict(
                reference="0092026",
                date=datetime.date(2026, 3, 4),
                client=C["ronix"],
                bc="003/2026",  # updated
                bc_date=None,
                mode="",
                amount_ht=D("65000.00"),
                amount_tva=D("5850.00"),
                amount_ttc=D("70850.00"),
                items=[
                    (
                        1,
                        "Formation IOSH Managing Safely",
                        PP,
                        D("1"),
                        D("1"),
                        D("65000.00"),
                    ),
                ],
            ),
            # ── 010 / A2M Electronics — ISO 9001 + Gestion Risques ────
            dict(
                reference="0102026",
                date=datetime.date(2026, 3, 4),
                client=C["a2m_electronics"],
                bc="04/2026",  # updated
                bc_date=None,
                mode="",
                amount_ht=D("402000.00"),
                amount_tva=D("36180.00"),
                amount_ttc=D("438180.00"),
                items=[
                    (1, "Formation ISO 9001", PD, D("1"), D("3"), D("63000.00")),
                    (
                        2,
                        "Formation Gestion des Risques",
                        PD,
                        D("1"),
                        D("3"),
                        D("63000.00"),
                    ),
                    (3, "Frais Pédagogique", PP, D("20"), D("1"), D("1200.00")),
                ],
            ),
            # ── 011 / Bait El Outour — Produits chimiques 4J ──────────
            dict(
                reference="0112026",
                date=datetime.date(2026, 3, 12),
                client=C["bait_el_outour"],
                bc="004/2026",  # updated (was 0019/2026)
                bc_date=None,
                mode=Invoice.PaymentMode.CHEQUE,
                amount_ht=D("200000.00"),
                amount_tva=D("18000.00"),
                amount_ttc=D("218000.00"),
                items=[
                    (
                        1,
                        "Formation Habilitation à la manipulation des produits chimiques",
                        PD,
                        D("1"),
                        D("4"),
                        D("50000.00"),
                    ),
                ],
            ),
            # ── 012 / Riadh El-Feth — Gestion du temps 4J ─────────────
            dict(
                reference="0122026",
                date=datetime.date(2026, 3, 26),
                client=C["riadh_el_feth"],
                bc="005/2026",  # updated
                bc_date=None,
                mode=Invoice.PaymentMode.CHEQUE,
                amount_ht=D("320000.00"),
                amount_tva=D("28800.00"),
                amount_ttc=D("348800.00"),
                items=[
                    (
                        1,
                        "Formation Maîtrise du Temps et Gestion des Priorités",
                        PD,
                        D("1"),
                        D("4"),
                        D("80000.00"),
                    ),
                ],
            ),
            # ── 013 / AFNES-Project — ISM-ATEX 2E × 3p ───────────────
            dict(
                reference="0132026",
                date=datetime.date(2026, 3, 26),
                client=C["afnes_project"],
                bc="006/2026",  # updated
                bc_date=None,
                mode=Invoice.PaymentMode.CHEQUE,
                amount_ht=D("540000.00"),
                amount_tva=D("48600.00"),
                amount_ttc=D("588600.00"),
                items=[
                    (1, "Formation ISM-ATEX 2E", PP, D("3"), D("1"), D("180000.00")),
                ],
            ),
            # ── 014 / Metal Steel — Chariots élévateurs 1p ────────────
            dict(
                reference="014/2026",
                date=datetime.date(2026, 3, 30),
                client=C["metal_steel"],
                bc="007/2026",  # updated
                bc_date=None,
                mode=Invoice.PaymentMode.CHEQUE,
                amount_ht=D("22000.00"),
                amount_tva=D("1980.00"),
                amount_ttc=D("23980.00"),
                items=[
                    (
                        1,
                        "Formation à la conduite de chariots élévateurs",
                        PP,
                        D("1"),
                        D("1"),
                        D("22000.00"),
                    ),
                ],
            ),
        ]

        created = 0
        for spec in specs:
            client = spec["client"]

            # Step 1: create invoice in PROFORMA / DRAFT
            inv = Invoice.objects.create(
                invoice_type=Invoice.InvoiceType.FORMATION,
                phase=Invoice.Phase.PROFORMA,
                status=Invoice.Status.DRAFT,
                client=client,
                invoice_date=spec["date"],
                tva_rate=TVA_9,
                bon_commande_number=spec["bc"],
                bon_commande_date=spec["bc_date"],
                mode_reglement=spec["mode"],
            )

            # Step 2: bulk-create items
            item_objs = []
            for order, desc, mode, nb_persons, nb_days, unit_price in spec["items"]:
                item = InvoiceItem(
                    invoice=inv,
                    order=order,
                    description=desc,
                    pricing_mode=mode,
                    nb_persons=nb_persons,
                    nb_days=nb_days,
                    unit_price_ht=unit_price,
                    total_ht=ZERO,
                )
                item.total_ht = item._compute_total_ht()
                item_objs.append(item)

            InvoiceItem.objects.bulk_create(item_objs)

            # Step 3: promote to FINALE and set exact amounts
            finalized_at = timezone.make_aware(
                datetime.datetime.combine(spec["date"], datetime.time(12, 0))
            )
            Invoice.objects.filter(pk=inv.pk).update(
                phase=Invoice.Phase.FINALE,
                status=Invoice.Status.UNPAID,
                reference=spec["reference"],
                finalized_at=finalized_at,
                amount_ht=spec["amount_ht"],
                amount_tva=spec["amount_tva"],
                amount_ttc=spec["amount_ttc"],
                amount_remaining=spec["amount_ttc"],
                # client snapshots
                client_name_snapshot=client.name,
                client_address_snapshot=client.address,
                client_type_snapshot=client.client_type,
                client_nif_snapshot=client.nif,
                client_nis_snapshot=getattr(client, "nis", ""),
                client_rc_snapshot=client.rc,
                client_ai_snapshot=client.article_imposition,
                client_nin_snapshot=client.nin,
                client_rib_snapshot=client.rib,
                client_tin_snapshot=client.tin,
            )
            created += 1
            self.stdout.write(f"    + {spec['reference']}  {client.name[:40]}")

        self.stdout.write(f"  ✓ {created} factures FORMATION finalisées")

    # ------------------------------------------------------------------ #
    # Sequence counters
    # ------------------------------------------------------------------ #
    def _update_sequences(self):
        """
        Align InvoiceSequence counters so the next invoice gets number 15.
        """
        for phase in (InvoiceSequence.Phase.PROFORMA, InvoiceSequence.Phase.FINALE):
            InvoiceSequence.objects.update_or_create(
                invoice_type=Invoice.InvoiceType.FORMATION,
                year=2026,
                phase=phase,
                defaults={"last_number": 14},
            )
        self.stdout.write(
            "  ✓ InvoiceSequence 2026 → dernier n° 14 (proforma & finale)"
        )

    # ------------------------------------------------------------------ #
    # Admin user
    # ------------------------------------------------------------------ #
    def _seed_admin_user(self):
        from django.contrib.auth.models import User
        from accounts.models import UserProfile

        username = "admin"
        email = "admin@example.com"
        password = "admin1234!"

        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                "email": email,
                "is_staff": True,
                "is_superuser": True,
            },
        )
        if created:
            user.set_password(password)
            user.save()
            self.stdout.write(f"  ✓ Admin user '{username}' créé.")
        else:
            # Update password if it changed
            if not user.check_password(password):
                user.set_password(password)
                user.save()
                self.stdout.write(f"  ✓ Mot de passe admin mis à jour.")

        # Ensure profile exists and is admin
        profile, created = UserProfile.objects.get_or_create(user=user)
        if created or profile.role != UserProfile.ROLE_ADMIN:
            profile.role = UserProfile.ROLE_ADMIN
            profile.save()
            if created:
                self.stdout.write(f"  ✓ Profil admin créé.")
            else:
                self.stdout.write(f"  ✓ Profil admin mis à jour.")
