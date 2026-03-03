# =============================================================================
# clients/admin.py  —  v3.0
# =============================================================================

from django.contrib import admin
from clients.models import Client, ClientContact


class ClientContactInline(admin.TabularInline):
    model = ClientContact
    extra = 0
    fields = ["first_name", "last_name", "job_title", "phone", "email", "is_primary"]


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "client_type",
        "city",
        "phone",
        "email",
        "activity_sector",
        "is_tva_exempt",
        "is_invoice_ready",
        "is_active",
    ]
    list_filter = ["client_type", "is_active", "is_tva_exempt", "city"]
    search_fields = ["name", "email", "phone", "rc", "nif", "nis", "nin"]
    list_editable = ["is_active"]
    readonly_fields = ["is_tva_exempt", "is_invoice_ready"]
    inlines = [ClientContactInline]
    fieldsets = [
        (
            "Identification",
            {
                "fields": [
                    "name",
                    "client_type",
                    "forme_juridique",
                    "activity_sector",
                    "is_active",
                ]
            },
        ),
        (
            "Coordonnées",
            {
                "fields": [
                    "address",
                    "postal_code",
                    "city",
                    "phone",
                    "email",
                    "website",
                ]
            },
        ),
        (
            "Contact principal (héritage)",
            {
                "fields": ["contact_name", "contact_phone", "contact_email"],
                "classes": ["collapse"],
            },
        ),
        (
            "Identifiants fiscaux",
            {
                "fields": [
                    "nin",
                    "nif",
                    "nis",
                    "rc",
                    "article_imposition",
                    "rib",
                    "is_tva_exempt",
                ],
                "description": (
                    "NIN : particulier uniquement. "
                    "NIF / A.I. : AE, entreprise, startup. "
                    "NIS / RC : entreprise, startup."
                ),
            },
        ),
        (
            "Auto-Entrepreneur",
            {
                "fields": ["carte_auto_entrepreneur"],
                "classes": ["collapse"],
            },
        ),
        (
            "Startup",
            {
                "fields": [
                    "label_startup_number",
                    "label_startup_date",
                    "programme_accompagnement",
                ],
                "classes": ["collapse"],
            },
        ),
        ("Statut facturation", {"fields": ["is_invoice_ready"]}),
        ("Notes", {"fields": ["notes"]}),
    ]

    @admin.display(description="Prêt facturation", boolean=True)
    def is_invoice_ready(self, obj):
        return obj.is_invoice_ready


@admin.register(ClientContact)
class ClientContactAdmin(admin.ModelAdmin):
    list_display = ["full_name", "client", "job_title", "phone", "email", "is_primary"]
    list_filter = ["is_primary"]
    search_fields = ["first_name", "last_name", "client__name", "email"]
    raw_id_fields = ["client"]
