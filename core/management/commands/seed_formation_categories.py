# formations/management/commands/seed_formation_categories.py
"""
Seed all 23 official professional branches (شعب مهنية) from the
2019 Algerian vocational training catalogue into FormationCategory.

Each entry:  (code, arabic_name, french_description, hex_color)

Run:
    python manage.py seed_formation_categories
    python manage.py seed_formation_categories --force   # overwrite names/colors
"""

from django.core.management.base import BaseCommand

# ── 23 official branches — طبعة 2019 ──────────────────────────────────── #
FORMATION_CATEGORIES = [
    (
        "ACP",
        "فن - ثقافة والتراث",
        "Arts, Culture et Patrimoine — restauration et conservation du patrimoine bâti, archéologie.",
        "#A16207",
    ),
    (
        "AGR",
        "الفلاحة",
        "Agriculture — productions végétales (maraîchage, arboriculture, grandes cultures, palmiers) "
        "et productions animales (bovins, ovins, caprins, volailles, apiculture).",
        "#15803D",
    ),
    (
        "AIG",
        "الفنون و الصناعة المطبعية",
        "Arts et Industrie Graphique — impression offset/flexo/hélio, édition, PAO, reliure.",
        "#6D28D9",
    ),
    (
        "ART",
        "الحرف التقليدية",
        "Artisanat Traditionnel — broderie, poterie, bijouterie, vannerie, sculpture sur bois/plâtre/marbre, "
        "tissage, verrerie, enluminure.",
        "#B45309",
    ),
    (
        "BAM",
        "الخشب و التأثيث",
        "Bois, Ameublement et Menuiserie — menuiserie architecturale, charpente, ébénisterie, "
        "marqueterie, constructions navales en bois.",
        "#92400E",
    ),
    (
        "BTP",
        "البناء والأشغال العمومية",
        "Bâtiment et Travaux Publics — gros œuvre, second œuvre, VRD, topographie, "
        "dessin technique, réhabilitation, isolation, énergies renouvelables.",
        "#1D4ED8",
    ),
    (
        "CIP",
        "الكيمياء الصناعية والبلاستيك",
        "Chimie Industrielle et Plastiques — transformation des plastiques et caoutchoucs, "
        "industrie papetière, verrerie, peintures/vernis, contrôle qualité chimique.",
        "#0E7490",
    ),
    (
        "CML",
        "الإنشاءات المعدنية",
        "Constructions Métalliques — soudage, chaudronnerie, menuiserie aluminium/PVC, "
        "peinture industrielle, structures métalliques, carrosserie.",
        "#374151",
    ),
    (
        "CMS",
        "الإنشاءات الميكانيكية والصناعة الحديدية",
        "Constructions Mécaniques et Sidérurgie — tournage, fraisage, rectification, "
        "fonderie, usinage CNC, métrologie, traitement des matériaux.",
        "#4B5563",
    ),
    (
        "CPX",
        "الصناعة الجلدية",
        "Industrie du Cuir — chaussures, maroquinerie, tannerie, sellerie, garniture automobile.",
        "#78350F",
    ),
    (
        "ELE",
        "الكهرباء – الإلكترونيك- طاقوية",
        "Électricité, Électronique et Énergies — installation électrique BT/HT, "
        "électronique industrielle/automobile, froid et climatisation, "
        "énergies solaires/éoliennes, domotique, ascenseurs.",
        "#F59E0B",
    ),
    (
        "HRT",
        "الفندقة - الإطعام و السياحة",
        "Hôtellerie, Restauration et Tourisme — cuisine (traditionnelle, gastronomique, collective), "
        "pâtisserie, boulangerie, service en salle, hébergement, réception, guidage touristique.",
        "#EC4899",
    ),
    (
        "IAA",
        "صناعة الأغذية الزراعية",
        "Industries Agro-Alimentaires — transformation des céréales, conserves, "
        "laiterie/fromagerie, dattes, corps gras, viandes, boissons, contrôle qualité IAA.",
        "#D97706",
    ),
    (
        "INP",
        "الصناعات النفطية",
        "Industries Pétrolières — forage, mesures, instrumentation de régulation, "
        "travaux de puits, sécurité industrielle pétrolière.",
        "#64748B",
    ),
    (
        "INT",
        "إعالم آلي – الرقمنة – الاتصالات",
        "Informatique, Numérique et Télécommunications — développement web/mobile, "
        "réseaux et cybersécurité, fibres optiques, cloud, data centers, VOIP, radiocommunications.",
        "#2563EB",
    ),
    (
        "MEE",
        "مهن المياه والبيئة",
        "Métiers de l'Eau et de l'Environnement — AEP, assainissement, traitement des eaux, "
        "gestion des déchets (ménagers, dangereux), barrages, infrastructures hydrotech.",
        "#0891B2",
    ),
    (
        "MES",
        "مهن الخدمات",
        "Métiers des Services — coiffure (hommes/femmes), esthétique, blanchisserie, "
        "optique-lunetterie, horlogerie, puériculture.",
        "#DB2777",
    ),
    (
        "MIC",
        "المناجم والمحاجر",
        "Mines et Carrières — extraction et abattage, forage, tir à l'explosif, "
        "topographie minière, traitement du minerai, sécurité minière.",
        "#6B7280",
    ),
    (
        "MME",
        "ميكانيك المحركات و الآليات",
        "Mécanique des Moteurs et Engins — mécanique auto VL/VI, engins de chantier/agricoles, "
        "hydraulique, injection diesel, conduite d'engins, mécatronique.",
        "#1F2937",
    ),
    (
        "PEC",
        "الصيد البحري و تربية المائيات",
        "Pêche et Aquaculture — pisciculture (eau douce/mer), ostréiculture, "
        "poissons ornementaux, traitement des produits de la pêche.",
        "#0369A1",
    ),
    (
        "TAG",
        "تقنيات الإدارة و التسيير",
        "Techniques d'Administration et de Gestion — comptabilité/finance, secrétariat, "
        "banques, assurances, commerce international, marketing, logistique, GRH, archivage.",
        "#7C3AED",
    ),
    (
        "TAV",
        "تقنيات السمعي البصري",
        "Techniques Audiovisuelles — image, son, montage, post-production, "
        "gestion de production, maintenance des équipements AV.",
        "#BE185D",
    ),
    (
        "THC",
        "النسيج و الألبسة",
        "Textile et Confection — filature, tissage, tricotage, teinture/finissage, "
        "coupe industrielle, confection (hommes/femmes), stylisme, mécanique des machines textiles.",
        "#9333EA",
    ),
]


class Command(BaseCommand):
    help = "Seed the 23 official professional branches (FormationCategory) from the 2019 Algerian vocational catalogue."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Overwrite name, description and color for existing entries.",
        )

    def handle(self, *args, **options):
        force = options["force"]

        try:
            from formations.models import FormationCategory
        except ImportError:
            self.stderr.write(
                self.style.ERROR(
                    "Could not import formations.models.FormationCategory — "
                    "make sure the formations app is installed and migrated."
                )
            )
            return

        created_count = 0
        updated_count = 0
        skipped_count = 0

        for code, name, description, color in FORMATION_CATEGORIES:
            obj, created = FormationCategory.objects.get_or_create(
                code=code,
                defaults={
                    "name": name,
                    "description": description,
                    "color": color,
                },
            )
            if created:
                created_count += 1
            elif force:
                obj.name = name
                obj.description = description
                obj.color = color
                obj.save(update_fields=["name", "description", "color", "updated_at"])
                updated_count += 1
            else:
                skipped_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"✓ FormationCategory — "
                f"{created_count} created, "
                f"{updated_count} updated, "
                f"{skipped_count} skipped "
                f"(total {len(FORMATION_CATEGORIES)} branches)."
            )
        )
        if skipped_count and not force:
            self.stdout.write(
                "  Tip: use --force to overwrite names/descriptions/colors for existing entries."
            )
