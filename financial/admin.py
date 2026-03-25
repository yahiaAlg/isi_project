# =============================================================================
# financial/admin.py  —  v3.1
# =============================================================================
# Changes in v3.1:
# * Invoice: mode_reglement field added to Règlement fieldset.
# * Invoice: timbre_fiscal, timbre_rate_display, amount_net_a_payer added
#   as readonly computed display fields.
# * Invoice: mode_reglement added to list_display.
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
    InvoiceSequence,
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
        if obj and obj.is_locked:
            return [f.name for f in InvoiceItem._meta.fields]
        return self.readonly_fields


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    fields = ["date", "amount", "method", "status", "reference"]

    def has_add_permission(self, request, obj=None):
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
        "mode_reglement",
        "amount_paid",
        "amount_remaining",
        "status",
        "has_bc_display",
        "is_overdue_display",
    ]
    list_filter = ["phase", "invoice_type", "status", "mode_reglement", "invoice_date"]
    search_fields = ["proforma_reference", "reference", "client__name"]
    raw_id_fields = ["client", "session", "study_project"]
    inlines = [InvoiceItemInline, PaymentInline]

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
        # v3.1 computed
        "timbre_fiscal",
        "timbre_rate_display",
        "amount_net_a_payer",
        # helpers
        "is_overdue_display",
        "days_overdue",
        "payment_completion_percent",
        "has_bc_display",
        "can_be_finalized",
        # client snapshots
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
                    "has_bc_display",
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
            "Règlement & timbre fiscal (v3.1)",
            {
                "fields": [
                    "mode_reglement",
                    "timbre_rate_display",
                    "timbre_fiscal",
                    "amount_net_a_payer",
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

    # ---- Custom list display columns --------------------------------- #

    @admin.display(description="Référence")
    def display_reference(self, obj):
        return obj.reference or obj.proforma_reference

    @admin.display(description="BC reçu", boolean=True)
    def has_bc_display(self, obj):
        return obj.has_bon_commande

    @admin.display(description="En retard", boolean=True)
    def is_overdue_display(self, obj):
        return obj.is_overdue

    # ---- Computed readonly fields (v3.1) ----------------------------- #

    @admin.display(description="Timbre fiscal (DA)")
    def timbre_fiscal(self, obj):
        value = obj.timbre_fiscal
        if value:
            return format_html("<strong>{} DA</strong>", value)
        return "—"

    @admin.display(description="Taux timbre")
    def timbre_rate_display(self, obj):
        return obj.timbre_rate_display or "—"

    @admin.display(description="Net à payer TTC (DA)")
    def amount_net_a_payer(self, obj):
        return obj.amount_net_a_payer

    @admin.display(description="Avancement paiement (%)")
    def payment_completion_percent(self, obj):
        return f"{obj.payment_completion_percent} %"

    @admin.display(description="Peut être finalisée", boolean=True)
    def can_be_finalized(self, obj):
        return obj.can_be_finalized

    @admin.display(description="Jours de retard")
    def days_overdue(self, obj):
        return obj.days_overdue or "—"


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

    @admin.display(description="Couverture (%)")
    def coverage_percent(self, obj):
        return f"{obj.coverage_percent} %"


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


# ---------------------------------------------------------------------------
# Invoice sequence (counter override)
# ---------------------------------------------------------------------------


@admin.register(InvoiceSequence)
class InvoiceSequenceAdmin(admin.ModelAdmin):
    """
    Allows operators to inspect and override the proforma / finale counters.
    Set `last_number` to N-1 so that the next invoice gets number N.
    Example: last_number = 4  →  next invoice = FP-005-2026.
    """

    list_display = [
        "__str__",
        "invoice_type",
        "phase",
        "year",
        "last_number",
        "next_number_display",
    ]
    list_editable = ["last_number"]
    list_filter = ["year", "invoice_type", "phase"]
    ordering = ["-year", "invoice_type", "phase"]

    @admin.display(description="Prochain n°")
    def next_number_display(self, obj):
        return format_html("<strong>{:03d}</strong>", obj.next_number)
