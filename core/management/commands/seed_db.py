"""
Management command: seed_db

Populates the database with a realistic base dataset for the ISI system.
Safe to run multiple times — uses get_or_create / update_or_create throughout.

Usage
-----
    python manage.py seed_db                  # full seed
    python manage.py seed_db --module accounts
    python manage.py seed_db --module clients
    python manage.py seed_db --module formations
    python manage.py seed_db --module resources
    python manage.py seed_db --module etudes
    python manage.py seed_db --module financial
    python manage.py seed_db --flush           # ⚠ wipes all data first
"""

import random
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify


# ─────────────────────────── helpers ──────────────────────────────────── #


def rand_date(start: date, end: date) -> date:
    delta = (end - start).days
    return start + timedelta(days=random.randint(0, delta))


def past(days: int) -> date:
    return date.today() - timedelta(days=days)


def future(days: int) -> date:
    return date.today() + timedelta(days=days)


# ─────────────────────────── raw seed data ────────────────────────────── #

INSTITUTE = {
    "name": "Institut de Sécurité Industrielle",
    "abbreviation": "ISI",
    "address": "12 Rue des Frères Bouadou, Bir Mourad Raïs",
    "postal_code": "16000",
    "city": "Alger",
    "phone": "023 56 78 90",
    "email": "contact@isi-algerie.dz",
    "website": "https://www.isi-algerie.dz",
    "registration_number": "16/00-1234567B19",
    "nif": "001623456789012",
    "nis": "162345678901234",
    "bank_name": "BNA — Agence Bir Mourad Raïs",
    "bank_account": "00200123456789",
    "bank_rib": "002 00100 00200123456789 56",
    "director_name": "Karim Messaoud",
    "director_title": "Directeur Général / Ingénieur HSE",
    "invoice_footer_text": (
        "Paiement à 30 jours à compter de la date de facturation. "
        "Tout retard de paiement entraîne des pénalités au taux légal en vigueur."
    ),
}

USERS = [
    {
        "username": "admin",
        "password": "admin1234!",
        "first_name": "Karim",
        "last_name": "Messaoud",
        "email": "k.messaoud@isi-algerie.dz",
        "role": "admin",
    },
    {
        "username": "receptionniste",
        "password": "recep1234!",
        "first_name": "Amira",
        "last_name": "Bensalem",
        "email": "a.bensalem@isi-algerie.dz",
        "role": "receptionist",
    },
]

CLIENTS = [
    {
        "name": "Sonatrach SPA",
        "client_type": "company",
        "city": "Alger",
        "address": "Djenane El Malik, Hydra",
        "postal_code": "16035",
        "phone": "021 54 60 00",
        "email": "hse@sonatrach.dz",
        "activity_sector": "Pétrole & Gaz",
        "registration_number": "16/00-5555001B19",
        "nif": "001600555500101",
        "nis": "160055550010123",
        "contact_name": "Mohamed Aït Saïd",
        "contact_phone": "0551 22 33 44",
        "contact_email": "m.aitsaid@sonatrach.dz",
    },
    {
        "name": "Cevital Industries",
        "client_type": "company",
        "city": "Béjaïa",
        "address": "Zone Industrielle, Port de Béjaïa",
        "postal_code": "06000",
        "phone": "034 22 50 00",
        "email": "securite@cevital.com",
        "activity_sector": "Agroalimentaire",
        "registration_number": "06/00-3333002B19",
        "nif": "000600333300201",
        "nis": "060033330020134",
        "contact_name": "Lynda Moussaoui",
        "contact_phone": "0661 44 55 66",
        "contact_email": "l.moussaoui@cevital.com",
    },
    {
        "name": "Groupe Hasnaoui",
        "client_type": "company",
        "city": "Sidi Bel Abbès",
        "address": "Route Nationale 7, Zone d'Activité",
        "postal_code": "22000",
        "phone": "048 75 10 10",
        "email": "direction@groupe-hasnaoui.dz",
        "activity_sector": "BTP / Construction",
        "registration_number": "22/00-7777003B19",
        "nif": "002200777700301",
        "nis": "220077770030145",
        "contact_name": "Rachid Hasnaoui",
        "contact_phone": "0771 88 99 00",
        "contact_email": "r.hasnaoui@groupe-hasnaoui.dz",
    },
    {
        "name": "Lafarge Algérie",
        "client_type": "company",
        "city": "M'Sila",
        "address": "Usine de Meftah — Zone Industrielle",
        "postal_code": "28000",
        "phone": "035 55 00 10",
        "email": "hse@lafarge.dz",
        "activity_sector": "Matériaux de Construction",
        "registration_number": "28/00-2222004B19",
        "nif": "002800222200401",
        "nis": "280022220040156",
        "contact_name": "Nadia Benali",
        "contact_phone": "0560 11 22 33",
        "contact_email": "n.benali@lafarge.dz",
    },
    {
        "name": "Entreprise Nationale des Travaux aux Puits — ENTP",
        "client_type": "company",
        "city": "Hassi Messaoud",
        "address": "BP 199, Hassi Messaoud",
        "postal_code": "30500",
        "phone": "029 73 00 01",
        "email": "securite@entp.dz",
        "activity_sector": "Services Pétroliers",
        "registration_number": "30/00-9999005B19",
        "nif": "003000999900501",
        "nis": "300099990050167",
        "contact_name": "Omar Zerrouki",
        "contact_phone": "0772 55 66 77",
        "contact_email": "o.zerrouki@entp.dz",
    },
    {
        "name": "Dr. Samy Belkacem",
        "client_type": "individual",
        "city": "Alger",
        "address": "15 Cité des Pins, El Biar",
        "postal_code": "16030",
        "phone": "0550 33 44 55",
        "email": "s.belkacem@gmail.com",
        "activity_sector": "Médecine du Travail",
    },
]

FORMATION_CATEGORIES = [
    {"name": "Sécurité Incendie", "color": "#EF4444"},
    {"name": "Travaux en Hauteur", "color": "#F97316"},
    {"name": "Risques Chimiques & ATEX", "color": "#EAB308"},
    {"name": "Secours & Premiers Secours", "color": "#22C55E"},
    {"name": "Santé & Sécurité au Travail (SST)", "color": "#3B82F6"},
    {"name": "Risques Électriques", "color": "#8B5CF6"},
    {"name": "Manutention & Équipements", "color": "#6B7280"},
]

FORMATIONS = [
    {
        "category": "Sécurité Incendie",
        "title": "Prévention et Lutte Contre l'Incendie",
        "description": "Formation théorique et pratique à la prévention incendie et à l'utilisation des extincteurs.",
        "objectives": "Identifier les classes de feu — Utiliser un extincteur — Organiser l'évacuation.",
        "target_audience": "Tous les employés d'entreprises industrielles.",
        "duration_days": 1,
        "duration_hours": 8,
        "base_price": Decimal("12000.00"),
        "max_participants": 20,
        "min_participants": 6,
    },
    {
        "category": "Travaux en Hauteur",
        "title": "Sécurité des Travaux en Hauteur",
        "description": "Formation complète sur la prévention des risques de chute lors des travaux en hauteur.",
        "objectives": "Maîtriser les EPI anti-chute — Planifier les travaux en sécurité — Appliquer la réglementation.",
        "target_audience": "Techniciens de maintenance, agents de chantier BTP.",
        "duration_days": 2,
        "duration_hours": 16,
        "base_price": Decimal("24000.00"),
        "max_participants": 15,
        "min_participants": 5,
    },
    {
        "category": "Risques Chimiques & ATEX",
        "title": "Gestion des Risques Chimiques en Milieu Industriel",
        "description": "Identification, évaluation et prévention des risques liés aux produits chimiques dangereux.",
        "objectives": "Lire une FDS — Choisir les EPI adaptés — Gérer un déversement accidentel.",
        "target_audience": "Agents de laboratoire, opérateurs en zone chimique.",
        "duration_days": 2,
        "duration_hours": 14,
        "base_price": Decimal("28000.00"),
        "max_participants": 12,
        "min_participants": 4,
    },
    {
        "category": "Secours & Premiers Secours",
        "title": "Sauveteur Secouriste du Travail (SST)",
        "description": "Formation certifiante SST conforme au référentiel national.",
        "objectives": "Protéger — Alerter — Secourir. Maîtriser les gestes de premiers secours.",
        "target_audience": "Tout personnel souhaitant obtenir le certificat SST.",
        "duration_days": 2,
        "duration_hours": 14,
        "base_price": Decimal("20000.00"),
        "max_participants": 10,
        "min_participants": 6,
        "accreditation_body": "Institut National du Travail",
        "accreditation_reference": "INT/SST/2024",
    },
    {
        "category": "Risques Électriques",
        "title": "Habilitation Électrique — Personnel Non Électricien",
        "description": "Préparation à l'habilitation électrique pour les non-électriciens travaillant à proximité d'installations BT.",
        "objectives": "Connaître les risques électriques — Respecter les consignations — Appliquer les prescriptions de sécurité.",
        "target_audience": "Opérateurs, agents de maintenance non-électriciens.",
        "duration_days": 1,
        "duration_hours": 7,
        "base_price": Decimal("15000.00"),
        "max_participants": 20,
        "min_participants": 5,
    },
    {
        "category": "Santé & Sécurité au Travail (SST)",
        "title": "Évaluation et Document Unique des Risques Professionnels",
        "description": "Méthode d'identification, d'évaluation et de transcription des risques professionnels dans le DUERP.",
        "objectives": "Rédiger un DUERP — Prioriser les actions préventives — Animer une démarche de prévention.",
        "target_audience": "Responsables HSE, chefs de service, membres du CSP.",
        "duration_days": 2,
        "duration_hours": 14,
        "base_price": Decimal("32000.00"),
        "max_participants": 16,
        "min_participants": 4,
    },
]

TRAINERS = [
    {
        "first_name": "Yacine",
        "last_name": "Bencherif",
        "specialty": "Sécurité Incendie, ATEX",
        "daily_rate": Decimal("15000.00"),
        "phone": "0555 11 22 33",
        "email": "y.bencherif@formateur-hse.dz",
    },
    {
        "first_name": "Farida",
        "last_name": "Hadj Mabrouk",
        "specialty": "Secours et Premiers Secours, SST",
        "daily_rate": Decimal("12000.00"),
        "phone": "0661 44 55 66",
        "email": "f.hadjmabrouk@gmail.com",
    },
    {
        "first_name": "Noureddine",
        "last_name": "Saïdi",
        "specialty": "Risques Électriques, Travaux en Hauteur",
        "daily_rate": Decimal("18000.00"),
        "phone": "0770 77 88 99",
        "email": "n.saidi@consult-elec.dz",
    },
]

ROOMS = [
    {
        "name": "Salle Atlas",
        "capacity": 25,
        "location": "Bâtiment Principal — RDC",
        "has_projector": True,
        "has_whiteboard": True,
        "has_ac": True,
    },
    {
        "name": "Salle Djurdjura",
        "capacity": 15,
        "location": "Bâtiment Principal — 1er étage",
        "has_projector": True,
        "has_whiteboard": True,
        "has_ac": True,
    },
    {
        "name": "Atelier Pratique",
        "capacity": 10,
        "location": "Annexe — RDC",
        "has_projector": False,
        "has_whiteboard": True,
        "has_ac": False,
    },
]

EQUIPMENT_LIST = [
    {
        "name": "Simulateur d'incendie électronique",
        "category": "Matériel pédagogique incendie",
        "serial_number": "SFE-2021-0042",
        "purchase_date": past(900),
        "purchase_cost": Decimal("180000.00"),
        "current_value": Decimal("120000.00"),
        "useful_life_years": 8,
        "maintenance_interval_days": 180,
        "condition": "good",
        "status": "active",
        "location": "Atelier Pratique",
    },
    {
        "name": "Détecteur de gaz multifonction GasAlertMax XT II",
        "category": "Détection & Mesure",
        "serial_number": "BW-MAXT-2022-0118",
        "purchase_date": past(600),
        "purchase_cost": Decimal("95000.00"),
        "current_value": Decimal("75000.00"),
        "useful_life_years": 5,
        "maintenance_interval_days": 90,
        "condition": "good",
        "status": "active",
        "location": "Salle Atlas",
    },
    {
        "name": "Kit mannequin RCP — Laerdal Little Anne x4",
        "category": "Matériel secourisme",
        "serial_number": "LRD-LA4-2020-0007",
        "purchase_date": past(1300),
        "purchase_cost": Decimal("60000.00"),
        "current_value": Decimal("30000.00"),
        "useful_life_years": 7,
        "maintenance_interval_days": 365,
        "condition": "good",
        "status": "active",
        "location": "Atelier Pratique",
    },
    {
        "name": "Vidéoprojecteur Epson EB-X51",
        "category": "Audiovisuel",
        "serial_number": "EPS-EBX51-2023-0003",
        "purchase_date": past(400),
        "purchase_cost": Decimal("55000.00"),
        "current_value": Decimal("48000.00"),
        "useful_life_years": 6,
        "maintenance_interval_days": 365,
        "condition": "good",
        "status": "active",
        "location": "Salle Atlas",
    },
    {
        "name": "Harnais anti-chute Miller H500 (lot de 5)",
        "category": "EPI Travaux en hauteur",
        "serial_number": "MLR-H500-2022-LOT5",
        "purchase_date": past(700),
        "purchase_cost": Decimal("45000.00"),
        "current_value": Decimal("28000.00"),
        "useful_life_years": 5,
        "maintenance_interval_days": 180,
        "condition": "needs_review",
        "status": "maintenance",
        "location": "Réserve Équipements",
    },
    {
        "name": "Luxmètre numérique Testo 540",
        "category": "Détection & Mesure",
        "serial_number": "TST-540-2019-0021",
        "purchase_date": past(1800),
        "purchase_cost": Decimal("22000.00"),
        "current_value": Decimal("5000.00"),
        "useful_life_years": 7,
        "maintenance_interval_days": 365,
        "condition": "needs_review",
        "status": "reserved",
        "location": "Bureau Ingénieur",
    },
]

EXPENSE_CATEGORIES_DATA = [
    {"name": "Transport & Déplacements", "is_direct_cost": True, "color": "#3B82F6"},
    {"name": "Matériel Consommable", "is_direct_cost": True, "color": "#F97316"},
    {"name": "Sous-traitance", "is_direct_cost": True, "color": "#8B5CF6"},
    {"name": "Loyer & Charges Locatives", "is_direct_cost": False, "color": "#6B7280"},
    {"name": "Télécommunications", "is_direct_cost": False, "color": "#06B6D4"},
    {"name": "Honoraires Formateurs", "is_direct_cost": True, "color": "#EAB308"},
    {"name": "Fournitures de Bureau", "is_direct_cost": False, "color": "#84CC16"},
    {"name": "Maintenance & Réparations", "is_direct_cost": False, "color": "#EF4444"},
    {"name": "Divers", "is_direct_cost": False, "color": "#9CA3AF"},
]

STUDY_PROJECTS = [
    {
        "client_name": "Sonatrach SPA",
        "title": "Audit HSE — Plateforme GNL Arzew",
        "project_type": "Audit HSE",
        "site_address": "Complexe GL2Z, Arzew, Oran",
        "start_date": past(120),
        "end_date": past(30),
        "budget": Decimal("850000.00"),
        "status": "completed",
        "priority": "high",
        "description": "Audit complet des systèmes de gestion HSE de la plateforme de liquéfaction GNL.",
        "phases": [
            {
                "name": "Collecte documentaire",
                "order": 1,
                "status": "completed",
                "estimated_hours": Decimal("16.0"),
                "actual_hours": Decimal("18.0"),
                "deliverable": "Rapport d'analyse documentaire",
                "start_date": past(120),
                "due_date": past(105),
                "completion_date": past(103),
            },
            {
                "name": "Visite terrain",
                "order": 2,
                "status": "completed",
                "estimated_hours": Decimal("24.0"),
                "actual_hours": Decimal("24.0"),
                "deliverable": "Rapport de visite avec photos",
                "start_date": past(100),
                "due_date": past(85),
                "completion_date": past(84),
            },
            {
                "name": "Analyse des écarts",
                "order": 3,
                "status": "completed",
                "estimated_hours": Decimal("20.0"),
                "actual_hours": Decimal("22.0"),
                "deliverable": "Rapport des non-conformités",
                "start_date": past(80),
                "due_date": past(60),
                "completion_date": past(58),
            },
            {
                "name": "Rapport final & plan d'action",
                "order": 4,
                "status": "completed",
                "estimated_hours": Decimal("16.0"),
                "actual_hours": Decimal("14.0"),
                "deliverable": "Rapport d'audit final + Plan d'actions correctives",
                "start_date": past(55),
                "due_date": past(35),
                "completion_date": past(32),
            },
        ],
    },
    {
        "client_name": "Lafarge Algérie",
        "title": "Étude des Risques ATEX — Unité de Broyage",
        "project_type": "Étude de risques ATEX",
        "site_address": "Usine de Meftah, M'Sila",
        "start_date": past(60),
        "end_date": future(30),
        "budget": Decimal("620000.00"),
        "status": "in_progress",
        "priority": "high",
        "description": "Identification et classification des zones ATEX dans l'unité de broyage du ciment.",
        "phases": [
            {
                "name": "Analyse documentaire & réglementaire",
                "order": 1,
                "status": "completed",
                "estimated_hours": Decimal("12.0"),
                "actual_hours": Decimal("11.0"),
                "deliverable": "Rapport bibliographique ATEX",
                "start_date": past(60),
                "due_date": past(48),
                "completion_date": past(46),
            },
            {
                "name": "Mesures et inventaire terrain",
                "order": 2,
                "status": "completed",
                "estimated_hours": Decimal("20.0"),
                "actual_hours": Decimal("21.0"),
                "deliverable": "Inventaire des sources de dégagement",
                "start_date": past(44),
                "due_date": past(28),
                "completion_date": past(25),
            },
            {
                "name": "Classification des zones & rapport ATEX",
                "order": 3,
                "status": "in_progress",
                "estimated_hours": Decimal("24.0"),
                "actual_hours": None,
                "deliverable": "Document de zonage ATEX + plans",
                "start_date": past(20),
                "due_date": future(10),
                "completion_date": None,
            },
        ],
    },
    {
        "client_name": "Groupe Hasnaoui",
        "title": "Diagnostic Sécurité — Chantier Tour B2",
        "project_type": "Diagnostic incendie & évacuation",
        "site_address": "Chantier Hai Es-Salam, Oran",
        "start_date": future(7),
        "end_date": future(60),
        "budget": Decimal("320000.00"),
        "status": "in_progress",
        "priority": "medium",
        "description": "Diagnostic des conditions de sécurité incendie et des procédures d'évacuation sur chantier.",
        "phases": [
            {
                "name": "Pré-diagnostic & planification",
                "order": 1,
                "status": "pending",
                "estimated_hours": Decimal("8.0"),
                "actual_hours": None,
                "deliverable": "Plan de mission validé",
                "start_date": future(7),
                "due_date": future(14),
                "completion_date": None,
            },
            {
                "name": "Visite diagnostic",
                "order": 2,
                "status": "pending",
                "estimated_hours": Decimal("16.0"),
                "actual_hours": None,
                "deliverable": "Rapport de visite",
                "start_date": future(15),
                "due_date": future(30),
                "completion_date": None,
            },
            {
                "name": "Rapport & recommandations",
                "order": 3,
                "status": "pending",
                "estimated_hours": Decimal("12.0"),
                "actual_hours": None,
                "deliverable": "Rapport final de diagnostic",
                "start_date": future(32),
                "due_date": future(58),
                "completion_date": None,
            },
        ],
    },
]


# ─────────────────────────── command ──────────────────────────────────── #


class Command(BaseCommand):
    help = "Seed the database with realistic base data for the ISI system."

    def add_arguments(self, parser):
        parser.add_argument(
            "--module",
            type=str,
            choices=[
                "accounts",
                "clients",
                "resources",
                "formations",
                "etudes",
                "financial",
            ],
            help="Seed only a specific module.",
        )
        parser.add_argument(
            "--flush",
            action="store_true",
            help="⚠ Flush all application data before seeding.",
        )

    def handle(self, *args, **options):
        if options["flush"]:
            self._flush()

        module = options.get("module")
        with transaction.atomic():
            if not module or module == "accounts":
                self._seed_accounts()
            if not module or module == "clients":
                self._seed_clients()
            if not module or module == "resources":
                self._seed_resources()
            if not module or module == "formations":
                self._seed_formations()
            if not module or module == "etudes":
                self._seed_etudes()
            if not module or module == "financial":
                self._seed_financial()

        self.stdout.write(self.style.SUCCESS("\n✔ Seed completed successfully."))

    # ------------------------------------------------------------------ #
    # Flush
    # ------------------------------------------------------------------ #

    def _flush(self):
        self.stdout.write(self.style.WARNING("Flushing application data…"))
        from financial.models import (
            CreditNote,
            Expense,
            ExpenseCategory,
            FinancialPeriod,
            Invoice,
            InvoiceItem,
            Payment,
        )
        from etudes.models import ProjectDeliverable, ProjectPhase, StudyProject
        from formations.models import (
            Attestation,
            Formation,
            FormationCategory,
            Participant,
            Session,
            Trainer,
            TrainingRoom,
        )
        from resources.models import (
            Equipment,
            EquipmentBooking,
            EquipmentUsage,
            MaintenanceLog,
        )
        from clients.models import Client, ClientContact
        from accounts.models import UserProfile

        for model in [
            CreditNote,
            Payment,
            InvoiceItem,
            Invoice,
            Expense,
            ExpenseCategory,
            FinancialPeriod,
            ProjectDeliverable,
            ProjectPhase,
            StudyProject,
            Attestation,
            Participant,
            Session,
            Formation,
            FormationCategory,
            EquipmentBooking,
            EquipmentUsage,
            MaintenanceLog,
            Equipment,
            Trainer,
            TrainingRoom,
            ClientContact,
            Client,
            UserProfile,
        ]:
            count, _ = model.objects.all().delete()
            self.stdout.write(f"  Deleted {count:>4} {model.__name__} records")

    # ------------------------------------------------------------------ #
    # Accounts
    # ------------------------------------------------------------------ #

    def _seed_accounts(self):
        from core.models import InstituteInfo, BureauEtudeInfo, FormationInfo
        from accounts.models import UserProfile

        self._log("Seeding institute configuration…")
        InstituteInfo.objects.update_or_create(pk=1, defaults=INSTITUTE)

        BureauEtudeInfo.objects.update_or_create(
            pk=1,
            defaults={
                "name": "Bureau d'Étude ISI",
                "invoice_prefix": "E",
                "tva_applicable": True,
                "tva_rate": Decimal("0.19"),
                "chief_engineer_name": "Karim Messaoud",
                "chief_engineer_title": "Ingénieur d'État en Hygiène et Sécurité Industrielle",
            },
        )

        FormationInfo.objects.update_or_create(
            pk=1,
            defaults={
                "name": "Centre de Formation ISI",
                "invoice_prefix": "F",
                "tva_applicable": True,
                "tva_rate": Decimal("0.19"),
                "attestation_validity_years": 5,
                "min_attendance_percent": 80,
                "director_name": "Karim Messaoud",
                "director_title": "Directeur — Institut de Sécurité Industrielle",
            },
        )

        self._log("Seeding users…")
        for u in USERS:
            user, created = User.objects.update_or_create(
                username=u["username"],
                defaults={
                    "first_name": u["first_name"],
                    "last_name": u["last_name"],
                    "email": u["email"],
                    "is_staff": u["role"] == "admin",
                    "is_superuser": u["role"] == "admin",
                },
            )
            if created or not user.has_usable_password():
                user.set_password(u["password"])
                user.save()

            UserProfile.objects.update_or_create(
                user=user,
                defaults={"role": u["role"], "is_active": True},
            )
            status = "created" if created else "updated"
            self._ok(f"  User '{u['username']}' {status}  [{u['role']}]")

    # ------------------------------------------------------------------ #
    # Clients
    # ------------------------------------------------------------------ #

    def _seed_clients(self):
        from clients.models import Client

        self._log("Seeding clients…")
        for data in CLIENTS:
            client, created = Client.objects.update_or_create(
                name=data["name"],
                defaults=data,
            )
            self._ok(f"  {'Created' if created else 'Updated'} client: {client.name}")

    # ------------------------------------------------------------------ #
    # Resources — trainers, rooms, equipment
    # ------------------------------------------------------------------ #

    def _seed_resources(self):
        from formations.models import Trainer, TrainingRoom
        from resources.models import Equipment, MaintenanceLog

        self._log("Seeding trainers…")
        for t in TRAINERS:
            trainer, created = Trainer.objects.update_or_create(
                email=t["email"], defaults=t
            )
            self._ok(
                f"  {'Created' if created else 'Updated'} trainer: {trainer.full_name}"
            )

        self._log("Seeding rooms…")
        for r in ROOMS:
            room, created = TrainingRoom.objects.update_or_create(
                name=r["name"], defaults=r
            )
            self._ok(f"  {'Created' if created else 'Updated'} room: {room.name}")

        self._log("Seeding equipment…")
        for e in EQUIPMENT_LIST:
            equip, created = Equipment.objects.update_or_create(
                serial_number=e["serial_number"], defaults=e
            )
            self._ok(f"  {'Created' if created else 'Updated'} equipment: {equip.name}")

            # Add an initial maintenance log for equipment that is due or past due
            if not equip.maintenance_logs.exists():
                last_maintenance_date = equip.purchase_date + timedelta(
                    days=equip.maintenance_interval_days
                )
                if last_maintenance_date <= date.today():
                    MaintenanceLog.objects.create(
                        equipment=equip,
                        date=last_maintenance_date,
                        maintenance_type="preventive",
                        cost=Decimal("5000.00"),
                        performed_by="Technicien interne",
                        description="Vérification périodique initiale post-acquisition.",
                        next_due_date=last_maintenance_date
                        + timedelta(days=equip.maintenance_interval_days),
                    )

    # ------------------------------------------------------------------ #
    # Formations — catalog + sessions + participants + attestations
    # ------------------------------------------------------------------ #

    def _seed_formations(self):
        from formations.models import (
            Attestation,
            Formation,
            FormationCategory,
            Participant,
            Session,
            Trainer,
            TrainingRoom,
        )

        self._log("Seeding formation categories…")
        cat_map = {}
        for c in FORMATION_CATEGORIES:
            cat, _ = FormationCategory.objects.update_or_create(
                name=c["name"], defaults=c
            )
            cat_map[c["name"]] = cat

        self._log("Seeding formation catalog…")
        formation_map = {}
        for f in FORMATIONS:
            cat_name = f.pop("category")
            slug = slugify(f["title"])
            formation, created = Formation.objects.update_or_create(
                slug=slug,
                defaults={**f, "category": cat_map[cat_name]},
            )
            formation_map[formation.title] = formation
            f["category"] = cat_name  # restore for idempotency
            self._ok(
                f"  {'Created' if created else 'Updated'} formation: {formation.title}"
            )

        # ---- Sessions ---- #
        self._log("Seeding sessions…")
        trainers = list(Trainer.objects.all())
        rooms = list(TrainingRoom.objects.all())

        session_specs = [
            # --- Completed sessions (invoiceable) ---
            {
                "formation": "Prévention et Lutte Contre l'Incendie",
                "client_name": "Sonatrach SPA",
                "date_start": past(90),
                "date_end": past(90),
                "status": "completed",
                "capacity": 20,
                "participants": [
                    ("Ahmed", "Benali", "Sonatrach SPA", True),
                    ("Fatima", "Cherif", "Sonatrach SPA", True),
                    ("Mourad", "Ziani", "Sonatrach SPA", True),
                    ("Nadia", "Hamdi", "Sonatrach SPA", True),
                    ("Kamel", "Bouzid", "Sonatrach SPA", False),  # absent
                ],
            },
            {
                "formation": "Sauveteur Secouriste du Travail (SST)",
                "client_name": "Cevital Industries",
                "date_start": past(65),
                "date_end": past(64),
                "status": "completed",
                "capacity": 10,
                "participants": [
                    ("Sara", "Moussaoui", "Cevital Industries", True),
                    ("Youcef", "Tighilt", "Cevital Industries", True),
                    ("Imane", "Kaci", "Cevital Industries", True),
                    ("Farid", "Ouali", "Cevital Industries", True),
                    ("Samia", "Alouani", "Cevital Industries", True),
                    ("Amine", "Boudiaf", "Cevital Industries", True),
                ],
            },
            {
                "formation": "Sécurité des Travaux en Hauteur",
                "client_name": "Groupe Hasnaoui",
                "date_start": past(45),
                "date_end": past(44),
                "status": "completed",
                "capacity": 15,
                "participants": [
                    ("Bilal", "Hadj Saïd", "Groupe Hasnaoui", True),
                    ("Redha", "Mekhalif", "Groupe Hasnaoui", True),
                    ("Lyes", "Ferhat", "Groupe Hasnaoui", True),
                    ("Khaled", "Mansouri", "Groupe Hasnaoui", True),
                ],
            },
            # --- Upcoming session ---
            {
                "formation": "Évaluation et Document Unique des Risques Professionnels",
                "client_name": "Lafarge Algérie",
                "date_start": future(14),
                "date_end": future(15),
                "status": "planned",
                "capacity": 16,
                "participants": [
                    ("Assia", "Benhamida", "Lafarge Algérie", True),
                    ("Tarek", "Sebbane", "Lafarge Algérie", True),
                    ("Souad", "Rahmani", "Lafarge Algérie", True),
                ],
            },
            # --- In-progress session ---
            {
                "formation": "Habilitation Électrique — Personnel Non Électricien",
                "client_name": "ENTP",
                "date_start": date.today(),
                "date_end": date.today(),
                "status": "in_progress",
                "capacity": 20,
                "participants": [
                    ("Omar", "Benchikh", "ENTP", True),
                    ("Walid", "Bacha", "ENTP", True),
                    ("Hakim", "Benbrahim", "ENTP", True),
                    ("Nabil", "Derrar", "ENTP", True),
                    ("Sonia", "Amirat", "ENTP", True),
                ],
            },
        ]

        from clients.models import Client

        for i, spec in enumerate(session_specs):
            formation = formation_map.get(spec["formation"])
            if not formation:
                continue

            client = Client.objects.filter(
                name__icontains=spec["client_name"].split()[0]
            ).first()
            trainer = trainers[i % len(trainers)] if trainers else None
            room = rooms[i % len(rooms)] if rooms else None

            session, created = Session.objects.get_or_create(
                formation=formation,
                date_start=spec["date_start"],
                client=client,
                defaults={
                    "date_end": spec["date_end"],
                    "trainer": trainer,
                    "room": room,
                    "status": spec["status"],
                    "capacity": spec["capacity"],
                    "price_per_participant": formation.base_price,
                },
            )

            action = "Created" if created else "Found"
            self._ok(f"  {action} session: {formation.title} ({spec['date_start']})")

            # Participants
            for first, last, employer, attended in spec["participants"]:
                participant, _ = Participant.objects.get_or_create(
                    session=session,
                    first_name=first,
                    last_name=last,
                    defaults={
                        "employer": employer,
                        "email": f"{first.lower()}.{last.lower().replace(' ', '')}@example.dz",
                        "attended": attended,
                    },
                )

                # Issue attestations for completed sessions with attending participants
                if (
                    session.status == "completed"
                    and attended
                    and not hasattr(participant, "attestation")
                ):
                    try:
                        Attestation.objects.get_or_create(
                            participant=participant,
                            defaults={
                                "session": session,
                                "issue_date": session.date_end,
                            },
                        )
                    except Exception:
                        pass  # reference collision is harmless here

    # ------------------------------------------------------------------ #
    # Études
    # ------------------------------------------------------------------ #

    def _seed_etudes(self):
        from clients.models import Client
        from etudes.models import ProjectPhase, StudyProject

        self._log("Seeding study projects…")
        for spec in STUDY_PROJECTS:
            client = Client.objects.filter(
                name__icontains=spec["client_name"].split()[0]
            ).first()
            if not client:
                self.stdout.write(
                    self.style.WARNING(
                        f"  Client '{spec['client_name']}' not found — skipping project."
                    )
                )
                continue

            phases_data = spec.pop("phases")
            client_name = spec.pop("client_name")

            project, created = StudyProject.objects.update_or_create(
                title=spec["title"],
                client=client,
                defaults={**spec, "client": client},
            )
            spec["client_name"] = client_name  # restore

            self._ok(
                f"  {'Created' if created else 'Updated'} project: {project.title}"
            )

            for ph in phases_data:
                ProjectPhase.objects.update_or_create(
                    project=project,
                    name=ph["name"],
                    defaults=ph,
                )

    # ------------------------------------------------------------------ #
    # Financial — expense categories, expenses, invoices, payments
    # ------------------------------------------------------------------ #

    def _seed_financial(self):
        from clients.models import Client
        from etudes.models import StudyProject
        from financial.models import (
            Expense,
            ExpenseCategory,
            FinancialPeriod,
            Invoice,
            InvoiceItem,
            Payment,
        )
        from formations.models import Session

        # ---- Expense categories ---- #
        self._log("Seeding expense categories…")
        cat_map = {}
        for c in EXPENSE_CATEGORIES_DATA:
            cat, _ = ExpenseCategory.objects.update_or_create(
                name=c["name"], defaults=c
            )
            cat_map[c["name"]] = cat

        # ---- Financial periods ---- #
        self._log("Seeding financial periods…")
        year = date.today().year
        FinancialPeriod.objects.update_or_create(
            name=f"Exercice {year}",
            defaults={
                "period_type": "year",
                "date_start": date(year, 1, 1),
                "date_end": date(year, 12, 31),
                "is_closed": False,
            },
        )
        if year > 2025:
            FinancialPeriod.objects.update_or_create(
                name=f"Exercice {year - 1}",
                defaults={
                    "period_type": "year",
                    "date_start": date(year - 1, 1, 1),
                    "date_end": date(year - 1, 12, 31),
                    "is_closed": True,
                },
            )

        # ---- Invoices for completed sessions ---- #
        self._log("Seeding invoices (formations)…")
        completed_sessions = Session.objects.filter(status="completed").select_related(
            "formation", "client"
        )
        transport_cat = cat_map["Transport & Déplacements"]
        honoraires_cat = cat_map["Honoraires Formateurs"]
        materiel_cat = cat_map["Matériel Consommable"]

        for session in completed_sessions:
            if not session.client:
                continue
            if Invoice.objects.filter(session=session).exists():
                continue

            invoice = Invoice.objects.create(
                invoice_type=Invoice.TYPE_FORMATION,
                client=session.client,
                invoice_date=session.date_end,
                due_date=session.date_end + timedelta(days=30),
                session=session,
            )

            attended = session.participants.filter(attended=True).count()
            InvoiceItem.objects.create(
                invoice=invoice,
                description=f"Formation « {session.formation.title} » — {attended} participant(s)",
                quantity=Decimal(str(attended)),
                unit="participant",
                unit_price_ht=session.effective_price,
                order=1,
            )

            self._ok(
                f"  Created invoice {invoice.reference} for session: {session.formation.title}"
            )

            # Add matching session expenses
            Expense.objects.get_or_create(
                date=session.date_start,
                description=f"Honoraires formateur — {session.formation.title}",
                defaults={
                    "category": honoraires_cat,
                    "amount": (
                        session.trainer.daily_rate * session.duration_days
                        if session.trainer
                        else Decimal("12000.00")
                    ),
                    "allocated_to_session": session,
                    "approval_status": "approved",
                },
            )
            Expense.objects.get_or_create(
                date=session.date_start,
                description=f"Matériel pédagogique — {session.formation.title}",
                defaults={
                    "category": materiel_cat,
                    "amount": Decimal("3500.00"),
                    "allocated_to_session": session,
                    "approval_status": "approved",
                },
            )

        # ---- Invoices for completed study projects ---- #
        self._log("Seeding invoices (études)…")
        completed_projects = StudyProject.objects.filter(
            status="completed"
        ).select_related("client")
        for project in completed_projects:
            if Invoice.objects.filter(study_project=project).exists():
                continue

            invoice = Invoice.objects.create(
                invoice_type=Invoice.TYPE_ETUDE,
                client=project.client,
                invoice_date=project.actual_end_date
                or project.end_date
                or date.today(),
                due_date=(project.actual_end_date or date.today()) + timedelta(days=30),
                study_project=project,
            )
            InvoiceItem.objects.create(
                invoice=invoice,
                description=f"Mission d'ingénierie HSE — {project.title}",
                quantity=Decimal("1.00"),
                unit="forfait",
                unit_price_ht=project.budget,
                order=1,
            )
            self._ok(
                f"  Created invoice {invoice.reference} for project: {project.title}"
            )

        # ---- Payments for invoices ---- #
        self._log("Seeding payments…")
        invoices = Invoice.objects.filter(
            status__in=[Invoice.STATUS_UNPAID, Invoice.STATUS_PARTIALLY_PAID]
        ).order_by("invoice_date")

        for i, invoice in enumerate(invoices):
            if i % 3 == 0:
                # Fully paid
                Payment.objects.get_or_create(
                    invoice=invoice,
                    date=invoice.invoice_date + timedelta(days=15),
                    defaults={
                        "amount": invoice.amount_ttc,
                        "method": Payment.METHOD_BANK_TRANSFER,
                        "status": Payment.STATUS_CONFIRMED,
                        "reference": f"VIR-{invoice.reference}",
                    },
                )
            elif i % 3 == 1:
                # Partial payment (50%)
                Payment.objects.get_or_create(
                    invoice=invoice,
                    date=invoice.invoice_date + timedelta(days=10),
                    defaults={
                        "amount": (invoice.amount_ttc / 2).quantize(Decimal("0.01")),
                        "method": Payment.METHOD_CHEQUE,
                        "status": Payment.STATUS_CONFIRMED,
                        "reference": f"CHQ-{invoice.reference}-01",
                    },
                )
            # i % 3 == 2 → left unpaid

        # ---- Overhead expenses ---- #
        self._log("Seeding overhead expenses…")
        loyer_cat = cat_map["Loyer & Charges Locatives"]
        telecom_cat = cat_map["Télécommunications"]
        bureau_cat = cat_map["Fournitures de Bureau"]

        overhead_expenses = [
            {
                "date": past(60),
                "category": loyer_cat,
                "description": "Loyer mensuel — locaux ISI",
                "amount": Decimal("45000.00"),
                "is_overhead": True,
                "approval_status": "approved",
            },
            {
                "date": past(30),
                "category": loyer_cat,
                "description": "Loyer mensuel — locaux ISI",
                "amount": Decimal("45000.00"),
                "is_overhead": True,
                "approval_status": "approved",
            },
            {
                "date": past(55),
                "category": telecom_cat,
                "description": "Abonnement Internet & téléphonie fixe",
                "amount": Decimal("8500.00"),
                "is_overhead": True,
                "approval_status": "approved",
            },
            {
                "date": past(50),
                "category": transport_cat,
                "description": "Déplacement Alger–Arzew (mission audit Sonatrach)",
                "amount": Decimal("12000.00"),
                "is_overhead": False,
                "allocated_to_project": StudyProject.objects.filter(
                    title__icontains="Arzew"
                ).first(),
                "approval_status": "approved",
            },
            {
                "date": past(20),
                "category": bureau_cat,
                "description": "Achats fournitures bureau et consommables imprimante",
                "amount": Decimal("6200.00"),
                "is_overhead": True,
                "approval_status": "approved",
                "receipt_missing": True,
            },
        ]

        for exp_data in overhead_expenses:
            # Skip if an expense with same date+description already exists
            if not Expense.objects.filter(
                date=exp_data["date"], description=exp_data["description"]
            ).exists():
                Expense.objects.create(**exp_data)

        self._ok(f"  Overhead expenses seeded.")

    # ------------------------------------------------------------------ #
    # Logging helpers
    # ------------------------------------------------------------------ #

    def _log(self, msg):
        self.stdout.write(f"\n{self.style.MIGRATE_HEADING(msg)}")

    def _ok(self, msg):
        self.stdout.write(self.style.SUCCESS(msg))
