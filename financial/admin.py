# =============================================================================
# financial/admin.py  —  v3.0
# =============================================================================

from django.contrib import admin
from django.utils.html import format_html
from financial.models import (
    CreditNote,
    Expense,
    ExpenseCategory,
    FinancialPeriod,
    Invoice,
    InvoiceItem,
    Payment,
)


# ---------------------------------------------------------------------------
# Inlines
# ---------------------------------------------------------------------------


class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 1
    fields = [
        "order",
        "description",
        "pricing_mode",
        "nb_persons",
        "nb_days",
        "unit_price_ht",
        "discount_percent",
        "total_ht",
    ]
    readonly_fields = ["total_ht"]

    def get_readonly_fields(self, request, obj=None):
        # Lock all item fields once the invoice is finalized
        if obj and obj.is_locked:
            return [f.name for f in InvoiceItem._meta.fields]
        return self.readonly_fields


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    fields = ["date", "amount", "method", "status", "reference"]

    def has_add_permission(self, request, obj=None):
        # Payments only allowed on finalized invoices
        if obj and not obj.is_payable:
            return False
        return super().has_add_permission(request, obj)


# ---------------------------------------------------------------------------
# Invoice
# ---------------------------------------------------------------------------


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = [
        "display_reference",
        "phase",
        "client",
        "invoice_type",
        "invoice_date",
        "amount_ttc",
        "amount_paid",
        "amount_remaining",
        "status",
        "has_bon_commande",
        "is_overdue_display",
    ]
    list_filter = ["phase", "invoice_type", "status", "invoice_date"]
    search_fields = ["proforma_reference", "reference", "client__name"]
    readonly_fields = [
        "proforma_reference",
        "reference",
        "phase",
        "finalized_at",
        "amount_ht",
        "amount_tva",
        "amount_ttc",
        "amount_paid",
        "amount_remaining",
        "amount_in_words",
        "is_overdue_display",
        "days_overdue",
        "payment_completion_percent",
        "has_bon_commande",
        "can_be_finalized",
        # Client snapshots
        "client_name_snapshot",
        "client_address_snapshot",
        "client_type_snapshot",
        "client_nif_snapshot",
        "client_nis_snapshot",
        "client_rc_snapshot",
        "client_ai_snapshot",
        "client_nin_snapshot",
        "client_rib_snapshot",
    ]
    raw_id_fields = ["client", "session", "study_project"]
    inlines = [InvoiceItemInline, PaymentInline]
    fieldsets = [
        (
            "Identification",
            {
                "fields": [
                    "proforma_reference",
                    "reference",
                    "page_ref",
                    "invoice_type",
                    "phase",
                    "status",
                    "client",
                ]
            },
        ),
        (
            "Dates",
            {
                "fields": [
                    "invoice_date",
                    "validity_date",
                    "due_date",
                    "finalized_at",
                ]
            },
        ),
        (
            "Bon de Commande",
            {
                "fields": [
                    "bon_commande_number",
                    "bon_commande_date",
                    "bon_commande_amount",
                    "bon_commande_scan",
                    "has_bon_commande",
                    "can_be_finalized",
                ]
            },
        ),
        ("Liens (traçabilité)", {"fields": ["session", "study_project"]}),
        (
            "Montants",
            {
                "fields": [
                    "tva_rate",
                    "amount_ht",
                    "amount_tva",
                    "amount_ttc",
                    "amount_paid",
                    "amount_remaining",
                    "amount_in_words",
                    "payment_completion_percent",
                ]
            },
        ),
        (
            "Snapshot client (figé à la finalisation)",
            {
                "fields": [
                    "client_name_snapshot",
                    "client_address_snapshot",
                    "client_type_snapshot",
                    "client_nif_snapshot",
                    "client_nis_snapshot",
                    "client_rc_snapshot",
                    "client_ai_snapshot",
                    "client_nin_snapshot",
                    "client_rib_snapshot",
                ],
                "classes": ["collapse"],
            },
        ),
        ("Textes", {"fields": ["notes", "footer_text"]}),
    ]

    @admin.display(description="Référence")
    def display_reference(self, obj):
        return obj.reference or obj.proforma_reference

    @admin.display(description="BC reçu", boolean=True)
    def has_bon_commande(self, obj):
        return obj.has_bon_commande

    @admin.display(description="En retard", boolean=True)
    def is_overdue_display(self, obj):
        return obj.is_overdue


# ---------------------------------------------------------------------------
# Payment
# ---------------------------------------------------------------------------


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ["invoice", "date", "amount", "method", "status", "reference"]
    list_filter = ["status", "method", "date"]
    search_fields = ["invoice__reference", "invoice__proforma_reference", "reference"]
    raw_id_fields = ["invoice"]


# ---------------------------------------------------------------------------
# Credit note
# ---------------------------------------------------------------------------


@admin.register(CreditNote)
class CreditNoteAdmin(admin.ModelAdmin):
    list_display = [
        "reference",
        "original_invoice",
        "date",
        "amount_ttc",
        "is_full_reversal",
    ]
    search_fields = ["reference", "original_invoice__reference"]
    readonly_fields = ["reference", "amount_tva", "amount_ttc", "coverage_percent"]
    raw_id_fields = ["original_invoice"]


# ---------------------------------------------------------------------------
# Expenses
# ---------------------------------------------------------------------------


@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "is_direct_cost", "color"]
    list_filter = ["is_direct_cost"]


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = [
        "date",
        "description",
        "category",
        "amount",
        "cost_centre_label",
        "approval_status",
        "receipt_missing",
        "needs_action",
    ]
    list_filter = ["approval_status", "category", "receipt_missing"]
    search_fields = ["description", "supplier"]
    raw_id_fields = ["allocated_to_session", "allocated_to_project"]
    readonly_fields = ["cost_centre_label", "needs_action", "is_approved"]
    fieldsets = [
        (
            "Dépense",
            {
                "fields": [
                    "date",
                    "category",
                    "description",
                    "amount",
                    "supplier",
                    "payment_reference",
                ]
            },
        ),
        (
            "Imputation",
            {
                "fields": [
                    "allocated_to_session",
                    "allocated_to_project",
                    "is_overhead",
                    "cost_centre_label",
                ]
            },
        ),
        ("Justificatif", {"fields": ["receipt", "receipt_missing"]}),
        (
            "Approbation",
            {"fields": ["approval_status", "approval_notes", "is_approved"]},
        ),
        ("Notes", {"fields": ["notes"]}),
    ]


# ---------------------------------------------------------------------------
# Financial period
# ---------------------------------------------------------------------------


@admin.register(FinancialPeriod)
class FinancialPeriodAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "period_type",
        "date_start",
        "date_end",
        "is_closed",
        "total_invoiced_ht",
        "total_collected",
        "gross_margin",
    ]
    list_filter = ["period_type", "is_closed"]
    readonly_fields = [
        "total_invoiced_ht",
        "total_collected",
        "total_expenses",
        "gross_margin",
        "formation_revenue_ht",
        "etude_revenue_ht",
    ]
