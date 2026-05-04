# financial/resources.py
# django-import-export resource definitions for the financial app.
#
# IMPORTANT DESIGN NOTES
# ──────────────────────
# * Invoice finalization logic (finalize()) must NOT be bypassed through
#   import. Importing a row with phase=finale will set the field values
#   directly in the DB without running business-rule validations.
#   Use imports only for migrating existing, already-finalized records.
#
# * Computed / denormalized amount fields (amount_tva, amount_ttc,
#   amount_remaining) are included in export for reference but are
#   protected from import via before_import_row() to prevent data
#   inconsistency — the model's own recalculate_amounts() is the
#   single source of truth.
#
# * FileField columns (bon_commande_scan) are excluded from import.

from import_export import fields, resources
from import_export.widgets import DecimalWidget, ForeignKeyWidget

from clients.models import Client
from etudes.models import StudyProject
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
from formations.models import Session

# ---------------------------------------------------------------------------
# ExpenseCategory
# ---------------------------------------------------------------------------


class ExpenseCategoryResource(resources.ModelResource):
    class Meta:
        model = ExpenseCategory
        fields = ("id", "name", "description", "is_direct_cost", "color")
        export_order = fields
        import_id_fields = ("name",)
        skip_unchanged = True
        report_skipped = False


# ---------------------------------------------------------------------------
# Invoice
# ---------------------------------------------------------------------------


class InvoiceResource(resources.ModelResource):
    client = fields.Field(
        column_name="client",
        attribute="client",
        widget=ForeignKeyWidget(Client, field="name"),
    )
    client_id = fields.Field(
        column_name="client_id",
        attribute="client",
        widget=ForeignKeyWidget(Client, field="id"),
    )
    session = fields.Field(
        column_name="session_id",
        attribute="session",
        widget=ForeignKeyWidget(Session, field="id"),
    )
    study_project = fields.Field(
        column_name="study_project_id",
        attribute="study_project",
        widget=ForeignKeyWidget(StudyProject, field="id"),
    )

    class Meta:
        model = Invoice
        fields = (
            # Identity
            "id",
            "invoice_type",
            "phase",
            "status",
            # References
            "proforma_reference",
            "reference",
            "page_ref",
            # Parties
            "client_id",
            "client",
            "session",
            "study_project",
            # Client snapshots (frozen at finalization — import-safe)
            "client_name_snapshot",
            "client_address_snapshot",
            "client_type_snapshot",
            "client_nif_snapshot",
            "client_nis_snapshot",
            "client_rc_snapshot",
            "client_ai_snapshot",
            "client_nin_snapshot",
            "client_rib_snapshot",
            "client_tin_snapshot",
            # Dates
            "invoice_date",
            "validity_date",
            "due_date",
            "finalized_at",
            # BC
            "bon_commande_number",
            "bon_commande_date",
            "bon_commande_amount",
            # Amounts
            "amount_ht",
            "tva_rate",
            "amount_tva",
            "amount_ttc",
            "amount_paid",
            "amount_remaining",
            "amount_in_words",
            # Payment mode
            "mode_reglement",
            # Notes
            "notes",
            "footer_text",
        )
        export_order = fields
        import_id_fields = ("proforma_reference",)
        skip_unchanged = True
        report_skipped = False
        # bon_commande_scan is a FileField — excluded from both import and export
        exclude = ("bon_commande_scan",)

    # Computed/denormalized fields that must not be overwritten on import;
    # they will be recalculated by the model's own methods.
    _PROTECTED_AMOUNT_FIELDS = frozenset(
        {"amount_tva", "amount_ttc", "amount_remaining"}
    )

    def before_import_row(self, row, row_number=None, **kwargs):
        """Normalise choice fields and strip protected computed columns."""
        for col in ("invoice_type", "phase", "status", "mode_reglement"):
            if col in row and row[col]:
                row[col] = str(row[col]).lower().strip()
        # Remove computed amounts so they are not written directly.
        for col in self._PROTECTED_AMOUNT_FIELDS:
            row.pop(col, None)


# ---------------------------------------------------------------------------
# InvoiceItem
# ---------------------------------------------------------------------------


class InvoiceItemResource(resources.ModelResource):
    invoice = fields.Field(
        column_name="invoice_proforma_ref",
        attribute="invoice",
        widget=ForeignKeyWidget(Invoice, field="proforma_reference"),
    )
    invoice_id = fields.Field(
        column_name="invoice_id",
        attribute="invoice",
        widget=ForeignKeyWidget(Invoice, field="id"),
    )

    class Meta:
        model = InvoiceItem
        fields = (
            "id",
            "invoice_id",
            "invoice",
            "order",
            "description",
            "pricing_mode",
            "nb_persons",
            "nb_days",
            "unit_price_ht",
            "discount_percent",
            "total_ht",
        )
        export_order = fields
        import_id_fields = ("id",)
        skip_unchanged = True
        report_skipped = False

    def before_import_row(self, row, row_number=None, **kwargs):
        if "pricing_mode" in row and row["pricing_mode"]:
            row["pricing_mode"] = str(row["pricing_mode"]).lower().strip()
        # total_ht is computed by model.save() — strip to avoid overwrite
        row.pop("total_ht", None)

    def save_instance(self, instance, is_new, row=None, **kwargs):
        """
        Bypass the is_locked guard during import.

        is_locked is a @property (data descriptor) that returns
        `self.phase == Phase.FINALE`. Data descriptors take precedence over
        instance __dict__, so shadowing via __dict__ does NOT work.

        The correct approach: temporarily swap phase to PROFORMA on the cached
        invoice instance before calling save(), then restore it. This makes
        is_locked return False for the duration of the save without touching
        the DB row (the invoice instance here is already loaded in memory;
        we never call invoice.save()).

        recalculate_amounts() is still invoked via the normal InvoiceItem.save()
        path, keeping Invoice totals correct.
        """
        invoice = instance.invoice
        original_phase = invoice.phase
        if invoice.phase == invoice.Phase.FINALE:
            invoice.phase = invoice.Phase.PROFORMA
        try:
            instance.save()
        finally:
            invoice.phase = original_phase


# ---------------------------------------------------------------------------
# Payment
# ---------------------------------------------------------------------------


class PaymentResource(resources.ModelResource):
    invoice = fields.Field(
        column_name="invoice_reference",
        attribute="invoice",
        widget=ForeignKeyWidget(Invoice, field="reference"),
    )
    invoice_id = fields.Field(
        column_name="invoice_id",
        attribute="invoice",
        widget=ForeignKeyWidget(Invoice, field="id"),
    )

    class Meta:
        model = Payment
        fields = (
            "id",
            "invoice_id",
            "invoice",
            "date",
            "amount",
            "method",
            "status",
            "reference",
            "notes",
        )
        export_order = fields
        import_id_fields = ("id",)
        skip_unchanged = True
        report_skipped = False

    def before_import_row(self, row, row_number=None, **kwargs):
        for col in ("method", "status"):
            if col in row and row[col]:
                row[col] = str(row[col]).lower().strip()


# ---------------------------------------------------------------------------
# CreditNote
# ---------------------------------------------------------------------------


class CreditNoteResource(resources.ModelResource):
    original_invoice = fields.Field(
        column_name="original_invoice_reference",
        attribute="original_invoice",
        widget=ForeignKeyWidget(Invoice, field="reference"),
    )
    original_invoice_id = fields.Field(
        column_name="original_invoice_id",
        attribute="original_invoice",
        widget=ForeignKeyWidget(Invoice, field="id"),
    )

    class Meta:
        model = CreditNote
        fields = (
            "id",
            "original_invoice_id",
            "original_invoice",
            "reference",
            "date",
            "reason",
            "amount_ht",
            "tva_rate",
            "amount_tva",
            "amount_ttc",
            "is_full_reversal",
            "notes",
        )
        export_order = fields
        import_id_fields = ("reference",)
        skip_unchanged = True
        report_skipped = False

    def before_import_row(self, row, row_number=None, **kwargs):
        # amount_tva and amount_ttc are computed in save(); strip them.
        for col in ("amount_tva", "amount_ttc"):
            row.pop(col, None)


# ---------------------------------------------------------------------------
# Expense
# ---------------------------------------------------------------------------


class ExpenseResource(resources.ModelResource):
    category = fields.Field(
        column_name="category",
        attribute="category",
        widget=ForeignKeyWidget(ExpenseCategory, field="name"),
    )
    allocated_to_session = fields.Field(
        column_name="session_id",
        attribute="allocated_to_session",
        widget=ForeignKeyWidget(Session, field="id"),
    )
    allocated_to_project = fields.Field(
        column_name="project_id",
        attribute="allocated_to_project",
        widget=ForeignKeyWidget(StudyProject, field="id"),
    )

    class Meta:
        model = Expense
        fields = (
            "id",
            "date",
            "category",
            "description",
            "amount",
            "supplier",
            "payment_reference",
            "allocated_to_session",
            "allocated_to_project",
            "is_overhead",
            "receipt_missing",
            "approval_status",
            "approval_notes",
            "notes",
        )
        export_order = fields
        import_id_fields = ("id",)
        skip_unchanged = True
        report_skipped = False
        # receipt (FileField) excluded from import
        exclude = ("receipt",)

    def before_import_row(self, row, row_number=None, **kwargs):
        if "approval_status" in row and row["approval_status"]:
            row["approval_status"] = str(row["approval_status"]).lower().strip()


# ---------------------------------------------------------------------------
# FinancialPeriod
# ---------------------------------------------------------------------------


class FinancialPeriodResource(resources.ModelResource):
    class Meta:
        model = FinancialPeriod
        fields = (
            "id",
            "name",
            "period_type",
            "date_start",
            "date_end",
            "is_closed",
            "notes",
        )
        export_order = fields
        import_id_fields = ("name",)
        skip_unchanged = True
        report_skipped = False


# ---------------------------------------------------------------------------
# InvoiceSequence
# ---------------------------------------------------------------------------


class InvoiceSequenceResource(resources.ModelResource):
    class Meta:
        model = InvoiceSequence
        fields = ("id", "invoice_type", "year", "phase", "last_number")
        export_order = fields
        import_id_fields = ("invoice_type", "year", "phase")
        skip_unchanged = True
        report_skipped = False
