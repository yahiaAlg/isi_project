# =============================================================================
# clients/admin.py
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
        "is_active",
    ]
    list_filter = ["client_type", "is_active", "city"]
    search_fields = ["name", "email", "phone", "registration_number", "nif", "nis"]
    list_editable = ["is_active"]
    inlines = [ClientContactInline]
    fieldsets = [
        (
            "Identification",
            {"fields": ["name", "client_type", "activity_sector", "is_active"]},
        ),
        (
            "Coordonnées",
            {"fields": ["address", "postal_code", "city", "phone", "email", "website"]},
        ),
        (
            "Contact principal",
            {"fields": ["contact_name", "contact_phone", "contact_email"]},
        ),
        ("Enregistrement", {"fields": ["registration_number", "nif", "nis"]}),
        ("Notes", {"fields": ["notes"]}),
    ]


@admin.register(ClientContact)
class ClientContactAdmin(admin.ModelAdmin):
    list_display = ["full_name", "client", "job_title", "phone", "email", "is_primary"]
    list_filter = ["is_primary"]
    search_fields = ["first_name", "last_name", "client__name", "email"]
    raw_id_fields = ["client"]
