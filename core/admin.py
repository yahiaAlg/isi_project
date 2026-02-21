# =============================================================================
# core/admin.py
# =============================================================================

from django.contrib import admin
from core.models import BureauEtudeInfo, FormationInfo, InstituteInfo


@admin.register(InstituteInfo)
class InstituteInfoAdmin(admin.ModelAdmin):
    fieldsets = [
        ("Identité", {"fields": ["name", "abbreviation", "logo"]}),
        (
            "Coordonnées",
            {"fields": ["address", "postal_code", "city", "phone", "email", "website"]},
        ),
        ("Enregistrement", {"fields": ["registration_number", "nif", "nis"]}),
        ("Banque", {"fields": ["bank_name", "bank_account", "bank_rib"]}),
        (
            "Direction",
            {"fields": ["director_name", "director_title", "director_signature"]},
        ),
        ("Factures", {"fields": ["invoice_footer_text"]}),
    ]

    def has_add_permission(self, request):
        return not InstituteInfo.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(FormationInfo)
class FormationInfoAdmin(admin.ModelAdmin):
    fieldsets = [
        ("Identité", {"fields": ["name", "description"]}),
        ("Coordonnées", {"fields": ["address", "phone", "email"]}),
        ("Facturation", {"fields": ["invoice_prefix", "tva_applicable", "tva_rate"]}),
        (
            "Direction",
            {"fields": ["director_name", "director_title", "director_signature"]},
        ),
        (
            "Attestations",
            {"fields": ["attestation_validity_years", "min_attendance_percent"]},
        ),
    ]

    def has_add_permission(self, request):
        return not FormationInfo.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(BureauEtudeInfo)
class BureauEtudeInfoAdmin(admin.ModelAdmin):
    fieldsets = [
        ("Identité", {"fields": ["name", "description"]}),
        ("Coordonnées", {"fields": ["address", "phone", "email"]}),
        ("Facturation", {"fields": ["invoice_prefix", "tva_applicable", "tva_rate"]}),
        (
            "Ingénieur en chef",
            {
                "fields": [
                    "chief_engineer_name",
                    "chief_engineer_title",
                    "chief_engineer_signature",
                ]
            },
        ),
    ]

    def has_add_permission(self, request):
        return not BureauEtudeInfo.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
