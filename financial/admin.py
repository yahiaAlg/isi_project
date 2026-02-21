# =============================================================================
# financial/admin.py
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


class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 1
    fields = [
        "order",
        "description",
        "quantity",
        "unit",
        "unit_price_ht",
        "discount_percent",
        "total_ht",
    ]
    readonly_fields = ["total_ht"]


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    fields = ["date", "amount", "method", "status", "reference"]
    readonly_fields = ["status"]


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = [
        "reference",
        "client",
        "invoice_type",
        "invoice_date",
        "amount_ttc",
        "amount_paid",
        "amount_remaining",
        "status",
        "is_overdue",
    ]
    list_filter = ["invoice_type", "status", "invoice_date"]
    search_fields = ["reference", "client__name"]
    readonly_fields = [
        "reference",
        "amount_ht",
        "amount_tva",
        "amount_ttc",
        "amount_paid",
        "amount_remaining",
        "is_overdue",
        "days_overdue",
        "client_name_snapshot",
        "client_address_snapshot",
        "client_nif_snapshot",
        "client_nis_snapshot",
        "client_rc_snapshot",
    ]
    raw_id_fields = ["client", "session", "study_project"]
    inlines = [InvoiceItemInline, PaymentInline]
    fieldsets = [
        (
            "Facture",
            {
                "fields": [
                    "reference",
                    "invoice_type",
                    "client",
                    "invoice_date",
                    "due_date",
                    "status",
                ]
            },
        ),
        ("Liens", {"fields": ["session", "study_project"]}),
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
                ]
            },
        ),
        (
            "Snapshot client",
            {
                "fields": [
                    "client_name_snapshot",
                    "client_address_snapshot",
                    "client_nif_snapshot",
                    "client_nis_snapshot",
                    "client_rc_snapshot",
                ],
                "classes": ["collapse"],
            },
        ),
        ("Textes", {"fields": ["notes", "footer_text"]}),
    ]

    @admin.display(description="En retard", boolean=True)
    def is_overdue(self, obj):
        return obj.is_overdue


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ["invoice", "date", "amount", "method", "status", "reference"]
    list_filter = ["status", "method"]
    search_fields = ["invoice__reference", "reference"]
    raw_id_fields = ["invoice"]


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
    readonly_fields = ["reference", "amount_tva", "amount_ttc"]
    raw_id_fields = ["original_invoice"]


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
    ]
    list_filter = ["approval_status", "category", "receipt_missing"]
    search_fields = ["description", "supplier"]
    raw_id_fields = ["allocated_to_session", "allocated_to_project"]
    readonly_fields = ["cost_centre_label", "needs_action"]
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
        ("Approbation", {"fields": ["approval_status", "approval_notes"]}),
        ("Notes", {"fields": ["notes"]}),
    ]


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
