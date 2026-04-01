# financial/management/commands/seed_expense_categories.py
#
# Usage:
#   python manage.py seed_expense_categories
#   python manage.py seed_expense_categories --clear   # drop existing first

from django.core.management.base import BaseCommand


CATEGORIES = [
    # ── Direct costs ─────────────────────────────────────────────────── #
    {
        "name": "Honoraires formateurs",
        "description": "Rémunération journalière des formateurs internes et externes.",
        "is_direct_cost": True,
        "color": "#3B82F6",
    },
    {
        "name": "Matériel pédagogique",
        "description": "Supports de cours, manuels, livrets, consommables de formation.",
        "is_direct_cost": True,
        "color": "#8B5CF6",
    },
    {
        "name": "Équipements de sécurité (PPE)",
        "description": "Équipements de protection individuelle utilisés en formation ou mission.",
        "is_direct_cost": True,
        "color": "#F59E0B",
    },
    {
        "name": "Location de salle",
        "description": "Location ponctuelle de salles de formation hors-site.",
        "is_direct_cost": True,
        "color": "#10B981",
    },
    {
        "name": "Transport & déplacements",
        "description": "Frais de transport, carburant, hébergement pour missions et formations.",
        "is_direct_cost": True,
        "color": "#06B6D4",
    },
    {
        "name": "Sous-traitance technique",
        "description": "Prestations de sous-traitants ou consultants externes sur projets d'étude.",
        "is_direct_cost": True,
        "color": "#EC4899",
    },
    {
        "name": "Maintenance équipements",
        "description": "Coûts de maintenance préventive et corrective du matériel pédagogique.",
        "is_direct_cost": True,
        "color": "#EF4444",
    },
    {
        "name": "Impression & reprographie",
        "description": "Impression de rapports, certificats, attestations et supports clients.",
        "is_direct_cost": True,
        "color": "#64748B",
    },
    # ── Overhead ─────────────────────────────────────────────────────── #
    {
        "name": "Loyer & charges locatives",
        "description": "Loyer des locaux de l'institut et charges associées.",
        "is_direct_cost": False,
        "color": "#6366F1",
    },
    {
        "name": "Fournitures de bureau",
        "description": "Papeterie, consommables informatiques, petit matériel administratif.",
        "is_direct_cost": False,
        "color": "#84CC16",
    },
    {
        "name": "Frais bancaires",
        "description": "Commissions bancaires, frais de tenue de compte, virements.",
        "is_direct_cost": False,
        "color": "#A3A3A3",
    },
    {
        "name": "Télécommunications",
        "description": "Abonnements téléphone, internet, messagerie professionnelle.",
        "is_direct_cost": False,
        "color": "#0EA5E9",
    },
    {
        "name": "Assurances",
        "description": "Assurance RC professionnelle, locaux, matériel.",
        "is_direct_cost": False,
        "color": "#F97316",
    },
    {
        "name": "Publicité & communication",
        "description": "Supports marketing, site web, annonces, participation aux salons.",
        "is_direct_cost": False,
        "color": "#D946EF",
    },
    {
        "name": "Taxes & impôts",
        "description": "TAP, IBS, autres taxes professionnelles hors TVA.",
        "is_direct_cost": False,
        "color": "#DC2626",
    },
    {
        "name": "Divers",
        "description": "Dépenses ne rentrant dans aucune catégorie définie.",
        "is_direct_cost": False,
        "color": "#94A3B8",
    },
]


class Command(BaseCommand):
    help = "Seed initial ExpenseCategory records for the financial module."

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete all existing ExpenseCategory records before seeding.",
        )

    def handle(self, *args, **options):
        from financial.models import ExpenseCategory

        if options["clear"]:
            deleted, _ = ExpenseCategory.objects.all().delete()
            self.stdout.write(
                self.style.WARNING(f"Deleted {deleted} existing category records.")
            )

        created_count = updated_count = 0
        for data in CATEGORIES:
            _, created = ExpenseCategory.objects.update_or_create(
                name=data["name"],
                defaults={k: v for k, v in data.items() if k != "name"},
            )
            if created:
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Done — {created_count} created, {updated_count} updated ({len(CATEGORIES)} total)."
            )
        )
