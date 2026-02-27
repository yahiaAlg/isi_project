"""
Financial models — Invoices, line items, payments, credit notes, expenses.

Design principles
-----------------
* Invoice → InvoiceItem (line items) replaces the single-amount design so that
  sessions with multiple participants, or projects with multiple deliverables,
  can be itemised on a single invoice.
* amount_paid / amount_remaining are maintained as real DB columns (updated by
  Payment.save / delete) so that Client.outstanding_balance can use a plain
  aggregate query instead of joining through payments at runtime.
* CreditNote is a first-class model rather than a flag on Invoice; it carries
  its own reference number and links back to the original invoice.
* Expense approval follows the spec: flag for missing receipt and pending
  approval, receipt upload, overhead vs allocated cost centre.
* All monetary fields use max_digits=14, decimal_places=2 (Algerian Dinar —
  large amounts are normal; no sub-unit precision needed).
"""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Sum
from django.utils import timezone

from clients.models import Client
from core.base_models import TimeStampedModel


# ======================================================================= #
# Invoice
# ======================================================================= #


class Invoice(TimeStampedModel):
    """
    An invoice issued to a client after service delivery.

    Business rules enforced here:
    - Formation invoices may only be created when the linked session is
      'completed'; this is checked in the view layer, not here.
    - Invoice numbers are auto-generated, sequential, and unique per
      business line (F-YYYY-NNN / E-YYYY-NNN).
    - TVA rate is snapshotted at creation time from the relevant
      FormationInfo / BureauEtudeInfo singleton.
    - amount_paid and amount_remaining are maintained by Payment signals so
      that aggregate queries on Client work with a single DB round-trip.
    """

    # ---- Business line ----------------------------------------------- #
    TYPE_FORMATION = "formation"
    TYPE_ETUDE = "etude"

    TYPE_CHOICES = [
        (TYPE_FORMATION, "Formation"),
        (TYPE_ETUDE, "Étude"),
    ]

    # ---- Payment status ---------------------------------------------- #
    STATUS_UNPAID = "unpaid"
    STATUS_PARTIALLY_PAID = "partially_paid"
    STATUS_PAID = "paid"
    STATUS_VOIDED = "voided"
    STATUS_CREDIT_NOTE = "credit_note"  # original invoice replaced by CN

    STATUS_CHOICES = [
        (STATUS_UNPAID, "Non payée"),
        (STATUS_PARTIALLY_PAID, "Partiellement payée"),
        (STATUS_PAID, "Payée"),
        (STATUS_VOIDED, "Annulée"),
        (STATUS_CREDIT_NOTE, "Avoir émis"),
    ]

    # ---- Core fields ------------------------------------------------- #
    invoice_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        verbose_name="Type",
    )
    reference = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="Numéro de facture",
        help_text="Ex. F-2026-001 ou E-2026-001 — généré automatiquement.",
    )
    client = models.ForeignKey(
        Client,
        on_delete=models.PROTECT,
        related_name="invoices",
        verbose_name="Client",
    )
    invoice_date = models.DateField(verbose_name="Date de facturation")
    due_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Date d'échéance",
        help_text="Laissez vide pour paiement comptant.",
    )

    # ---- Links to business objects (optional but useful) -------------- #
    session = models.ForeignKey(
        "formations.Session",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invoices",
        verbose_name="Session",
    )
    study_project = models.ForeignKey(
        "etudes.StudyProject",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invoices",
        verbose_name="Projet d'étude",
    )

    # ---- Snapshot of client info at invoice time --------------------- #
    # Stored so that editing the client later does not alter printed invoices.
    client_name_snapshot = models.CharField(
        max_length=255, blank=True, verbose_name="Nom client (snapshot)"
    )
    client_address_snapshot = models.TextField(
        blank=True, verbose_name="Adresse client (snapshot)"
    )
    client_nif_snapshot = models.CharField(
        max_length=100, blank=True, verbose_name="NIF client (snapshot)"
    )
    client_nis_snapshot = models.CharField(
        max_length=100, blank=True, verbose_name="NIS client (snapshot)"
    )
    client_rc_snapshot = models.CharField(
        max_length=100, blank=True, verbose_name="RC client (snapshot)"
    )

    # ---- Amounts (all in DA) ----------------------------------------- #
    amount_ht = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Montant HT (DA)",
    )
    tva_rate = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        default=Decimal("0.19"),
        verbose_name="Taux TVA",
    )
    amount_tva = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Montant TVA (DA)",
    )
    amount_ttc = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Montant TTC (DA)",
    )

    # Maintained by Payment.save() / delete() — used in Client aggregate queries
    amount_paid = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Montant payé (DA)",
    )
    amount_remaining = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Reste à payer (DA)",
    )

    # ---- Status ------------------------------------------------------ #
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_UNPAID,
        verbose_name="Statut",
    )

    # ---- Notes & footer --------------------------------------------- #
    notes = models.TextField(blank=True, verbose_name="Notes internes")
    # Override the institute-level footer for this specific invoice if needed
    footer_text = models.TextField(
        blank=True, verbose_name="Pied de page (personnalisé)"
    )

    class Meta:
        verbose_name = "Facture"
        verbose_name_plural = "Factures"
        ordering = ["-invoice_date", "-reference"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["client", "status"]),
            models.Index(fields=["invoice_type", "invoice_date"]),
        ]

    def __str__(self):
        return f"{self.reference} — {self.client.name}"

    # ------------------------------------------------------------------ #
    # Auto-reference generation
    # ------------------------------------------------------------------ #

    @classmethod
    def _next_reference(cls, invoice_type, year):
        """
        Generate the next sequential reference for a given type and year.
        Uses select_for_update inside a transaction to prevent gaps or
        duplicates under concurrent saves.
        """
        from core.models import BureauEtudeInfo, FormationInfo

        if invoice_type == cls.TYPE_FORMATION:
            prefix = FormationInfo.get_instance().invoice_prefix or "F"
        else:
            prefix = BureauEtudeInfo.get_instance().invoice_prefix or "E"

        with transaction.atomic():
            count = (
                cls.objects.select_for_update()
                .filter(invoice_type=invoice_type, invoice_date__year=year)
                .count()
            ) + 1
        return f"{prefix}-{year}-{count:03d}"

    # ------------------------------------------------------------------ #
    # Amount calculation
    # ------------------------------------------------------------------ #

    def recalculate_amounts(self):
        """
        Recompute HT from line items, then derive TVA and TTC.
        Should be called whenever InvoiceItems are added or changed.
        """
        total_ht = self.items.aggregate(total=Sum("total_ht"))["total"] or Decimal("0")
        self.amount_ht = total_ht
        self.amount_tva = (total_ht * self.tva_rate).quantize(Decimal("0.01"))
        self.amount_ttc = self.amount_ht + self.amount_tva
        self.amount_remaining = self.amount_ttc - self.amount_paid
        self.save(
            update_fields=["amount_ht", "amount_tva", "amount_ttc", "amount_remaining"]
        )

    def refresh_payment_totals(self):
        """
        Recompute amount_paid and amount_remaining from the payments table.
        Called by Payment.save() and Payment.delete().
        """
        paid = self.payments.filter(status=Payment.STATUS_CONFIRMED).aggregate(
            total=Sum("amount")
        )["total"] or Decimal("0")
        self.amount_paid = paid
        self.amount_remaining = max(self.amount_ttc - paid, Decimal("0"))
        # Derive status
        if self.status in [self.STATUS_VOIDED, self.STATUS_CREDIT_NOTE]:
            pass  # Don't touch voided / credit-noted invoices
        elif self.amount_remaining <= 0:
            self.status = self.STATUS_PAID
        elif self.amount_paid > 0:
            self.status = self.STATUS_PARTIALLY_PAID
        else:
            self.status = self.STATUS_UNPAID
        self.save(update_fields=["amount_paid", "amount_remaining", "status"])

    def save(self, *args, **kwargs):
        # Populate snapshot fields on first save
        if not self.pk:
            self.client_name_snapshot = self.client.name
            self.client_address_snapshot = self.client.address
            self.client_nif_snapshot = self.client.nif
            self.client_nis_snapshot = self.client.nis
            self.client_rc_snapshot = self.client.registration_number
        # Auto-generate reference
        if not self.reference:
            year = (self.invoice_date or timezone.now().date()).year
            self.reference = self._next_reference(self.invoice_type, year)
        super().save(*args, **kwargs)

    # ------------------------------------------------------------------ #
    # Status helpers
    # ------------------------------------------------------------------ #

    @property
    def is_overdue(self):
        return (
            self.due_date
            and self.due_date < timezone.now().date()
            and self.status in [self.STATUS_UNPAID, self.STATUS_PARTIALLY_PAID]
        )

    @property
    def days_overdue(self):
        if not self.is_overdue:
            return 0
        return (timezone.now().date() - self.due_date).days

    @property
    def is_payable(self):
        return self.status in [self.STATUS_UNPAID, self.STATUS_PARTIALLY_PAID]

    @property
    def payment_completion_percent(self):
        if not self.amount_ttc:
            return 0
        return round((self.amount_paid / self.amount_ttc) * 100, 1)

    def void(self, reason: str = ""):
        """
        Mark the invoice as voided. A voided invoice cannot receive payments.
        Prefer issuing a CreditNote over voiding when possible.
        """
        if self.status == self.STATUS_PAID:
            raise ValidationError(
                "Impossible d'annuler une facture déjà payée intégralement. "
                "Émettez un avoir à la place."
            )
        self.status = self.STATUS_VOIDED
        if reason:
            self.notes = f"[ANNULÉ] {reason}\n\n{self.notes}".strip()
        self.save(update_fields=["status", "notes"])


# ======================================================================= #
# Invoice line items
# ======================================================================= #


class InvoiceItem(TimeStampedModel):
    """
    A single line on an invoice.

    Separating line items from the invoice header allows invoices that span
    multiple participants, multiple training days, or multiple project phases
    to be itemised cleanly — matching what a professional invoice should show.
    """

    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name="Facture",
    )
    description = models.CharField(max_length=500, verbose_name="Désignation")
    quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("1.00"),
        verbose_name="Quantité",
    )
    unit = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Unité",
        help_text="Ex. participant, jour, heure, forfait.",
    )
    unit_price_ht = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        verbose_name="Prix unitaire HT (DA)",
    )
    # Optional line-level discount
    discount_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Remise (%)",
    )
    total_ht = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        verbose_name="Total HT (DA)",
        help_text="Calculé automatiquement.",
    )

    # Optional link to help with reporting
    session = models.ForeignKey(
        "formations.Session",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invoice_items",
        verbose_name="Session liée",
    )
    project_phase = models.ForeignKey(
        "etudes.ProjectPhase",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invoice_items",
        verbose_name="Phase liée",
    )

    order = models.PositiveIntegerField(default=1, verbose_name="Ordre")

    class Meta:
        verbose_name = "Ligne de facture"
        verbose_name_plural = "Lignes de facture"
        ordering = ["invoice", "order"]

    def __str__(self):
        return f"{self.invoice.reference} — {self.description}"

    def save(self, *args, **kwargs):
        # Recompute line total before saving
        base = self.quantity * self.unit_price_ht
        discount = base * (self.discount_percent / Decimal("100"))
        self.total_ht = (base - discount).quantize(Decimal("0.01"))
        super().save(*args, **kwargs)
        # Cascade up to the invoice header
        self.invoice.recalculate_amounts()

    def delete(self, *args, **kwargs):
        invoice = self.invoice
        super().delete(*args, **kwargs)
        invoice.recalculate_amounts()


# ======================================================================= #
# Payments
# ======================================================================= #


class Payment(TimeStampedModel):
    """
    A single payment instalment against an invoice.
    Supports partial payments; multiple Payment records per Invoice are allowed.
    """

    METHOD_CASH = "cash"
    METHOD_BANK_TRANSFER = "bank_transfer"
    METHOD_CHEQUE = "cheque"
    METHOD_OTHER = "other"

    METHOD_CHOICES = [
        (METHOD_CASH, "Espèces"),
        (METHOD_BANK_TRANSFER, "Virement bancaire"),
        (METHOD_CHEQUE, "Chèque"),
        (METHOD_OTHER, "Autre"),
    ]

    STATUS_PENDING = "pending"  # Cheque received but not yet cleared
    STATUS_CONFIRMED = "confirmed"  # Cleared / confirmed
    STATUS_REVERSED = "reversed"  # Chargeback or reversal

    STATUS_CHOICES = [
        (STATUS_PENDING, "En attente"),
        (STATUS_CONFIRMED, "Confirmé"),
        (STATUS_REVERSED, "Annulé / retourné"),
    ]

    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name="payments",
        verbose_name="Facture",
    )
    date = models.DateField(verbose_name="Date de paiement")
    amount = models.DecimalField(
        max_digits=14, decimal_places=2, verbose_name="Montant (DA)"
    )
    method = models.CharField(
        max_length=20,
        choices=METHOD_CHOICES,
        default=METHOD_BANK_TRANSFER,
        verbose_name="Mode de paiement",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_CONFIRMED,
        verbose_name="Statut",
    )
    # Bank / cheque reference number
    reference = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Référence",
        help_text="Numéro de virement, numéro de chèque, etc.",
    )
    notes = models.TextField(blank=True, verbose_name="Notes")

    class Meta:
        verbose_name = "Paiement"
        verbose_name_plural = "Paiements"
        ordering = ["-date"]

    def __str__(self):
        return f"Paiement {self.amount} DA — {self.invoice.reference} ({self.date})"

    def clean(self):
        if not self.invoice_id:
            return
        # Only block NEW payments on a closed invoice — edits to existing
        # payments must always be allowed (e.g. correcting a status)
        if self.pk is None and not self.invoice.is_payable:
            raise ValidationError(
                f"La facture {self.invoice.reference} n'est pas en attente de paiement."
            )
        if self.amount and self.amount <= 0:
            raise ValidationError("Le montant doit être positif.")
        # Warn if this payment would overpay the invoice
        already_paid = self.invoice.amount_paid
        if self.pk:
            # Exclude self when editing
            already_paid -= (
                Payment.objects.filter(pk=self.pk)
                .values_list("amount", flat=True)
                .first()
                or 0
            )
        if self.amount and (already_paid + self.amount) > self.invoice.amount_ttc:
            raise ValidationError(
                f"Ce paiement ({self.amount} DA) dépasserait le montant total de la "
                f"facture ({self.invoice.amount_ttc} DA)."
            )

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.invoice.refresh_payment_totals()

    def delete(self, *args, **kwargs):
        invoice = self.invoice
        super().delete(*args, **kwargs)
        invoice.refresh_payment_totals()

    @property
    def is_confirmed(self):
        return self.status == self.STATUS_CONFIRMED


# ======================================================================= #
# Credit notes
# ======================================================================= #


class CreditNote(TimeStampedModel):
    """
    A credit note (avoir) issued to partially or fully reverse an invoice.

    A CreditNote is not an Invoice subclass; it is a separate document that
    references the original invoice and carries its own reference number.
    The original invoice's status is set to STATUS_CREDIT_NOTE when a full
    credit note is issued.
    """

    original_invoice = models.ForeignKey(
        Invoice,
        on_delete=models.PROTECT,
        related_name="credit_notes",
        verbose_name="Facture d'origine",
    )
    reference = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="Numéro d'avoir",
        help_text="Généré automatiquement (ex. AV-2026-001).",
    )
    date = models.DateField(verbose_name="Date")
    reason = models.TextField(verbose_name="Motif")
    amount_ht = models.DecimalField(
        max_digits=14, decimal_places=2, verbose_name="Montant HT (DA)"
    )
    tva_rate = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        default=Decimal("0.19"),
        verbose_name="Taux TVA",
    )
    amount_tva = models.DecimalField(
        max_digits=14, decimal_places=2, verbose_name="Montant TVA (DA)"
    )
    amount_ttc = models.DecimalField(
        max_digits=14, decimal_places=2, verbose_name="Montant TTC (DA)"
    )
    # True = full reversal; False = partial credit
    is_full_reversal = models.BooleanField(
        default=False, verbose_name="Annulation totale"
    )
    notes = models.TextField(blank=True, verbose_name="Notes")

    class Meta:
        verbose_name = "Avoir"
        verbose_name_plural = "Avoirs"
        ordering = ["-date"]

    def __str__(self):
        return f"{self.reference} — avoir sur {self.original_invoice.reference}"

    @classmethod
    def _next_reference(cls, year):
        with transaction.atomic():
            count = (
                cls.objects.select_for_update().filter(date__year=year).count()
            ) + 1
        return f"AV-{year}-{count:03d}"

    def save(self, *args, **kwargs):
        if not self.reference:
            year = (self.date or timezone.now().date()).year
            self.reference = self._next_reference(year)
        # Derive TVA + TTC
        self.amount_tva = (self.amount_ht * self.tva_rate).quantize(Decimal("0.01"))
        self.amount_ttc = self.amount_ht + self.amount_tva
        super().save(*args, **kwargs)
        # Update original invoice status if full reversal
        if self.is_full_reversal:
            Invoice.objects.filter(pk=self.original_invoice_id).update(
                status=Invoice.STATUS_CREDIT_NOTE
            )

    @property
    def coverage_percent(self):
        """What percentage of the original invoice does this credit note cover."""
        if not self.original_invoice.amount_ttc:
            return 0
        return round((self.amount_ttc / self.original_invoice.amount_ttc) * 100, 1)


# ======================================================================= #
# Expenses
# ======================================================================= #


class ExpenseCategory(TimeStampedModel):
    """
    Configurable expense category (replaces hard-coded choices).
    Pre-populated with the categories from the spec; the owner can add more.
    """

    PRESET_TRANSPORT = "transport"
    PRESET_MATERIEL = "materiel_consommable"
    PRESET_SOUS_TRAITANCE = "sous_traitance"
    PRESET_LOYER = "loyer"
    PRESET_TELECOM = "telecommunications"
    PRESET_DIVERS = "divers"

    name = models.CharField(max_length=100, unique=True, verbose_name="Catégorie")
    description = models.TextField(blank=True, verbose_name="Description")
    # Used for grouping in reports
    is_direct_cost = models.BooleanField(
        default=True,
        verbose_name="Coût direct",
        help_text="Coût direct = imputable à un service. Indirect = frais généraux.",
    )
    color = models.CharField(
        max_length=7, default="#6B7280", verbose_name="Couleur (hex)"
    )

    class Meta:
        verbose_name = "Catégorie de dépense"
        verbose_name_plural = "Catégories de dépenses"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Expense(TimeStampedModel):
    """
    An operational expenditure incurred by the institute.

    Allocation model
    ----------------
    Each expense is allocated to exactly one of three cost centres:
    - A formation session  (allocated_to_session)
    - A study project      (allocated_to_project)
    - Overhead             (is_overhead = True)
    Enforced by clean().
    """

    # ---- Approval workflow ------------------------------------------ #
    APPROVAL_PENDING = "pending"
    APPROVAL_APPROVED = "approved"
    APPROVAL_REJECTED = "rejected"

    APPROVAL_CHOICES = [
        (APPROVAL_PENDING, "En attente"),
        (APPROVAL_APPROVED, "Approuvée"),
        (APPROVAL_REJECTED, "Refusée"),
    ]

    # ---- Core fields ------------------------------------------------- #
    date = models.DateField(verbose_name="Date")
    category = models.ForeignKey(
        ExpenseCategory,
        on_delete=models.PROTECT,
        related_name="expenses",
        verbose_name="Catégorie",
    )
    description = models.CharField(max_length=500, verbose_name="Description")
    amount = models.DecimalField(
        max_digits=14, decimal_places=2, verbose_name="Montant (DA)"
    )
    # Optional: which supplier / payee
    supplier = models.CharField(
        max_length=255, blank=True, verbose_name="Fournisseur / bénéficiaire"
    )
    # Payment reference (bank transfer number, cheque, etc.)
    payment_reference = models.CharField(
        max_length=100, blank=True, verbose_name="Référence de paiement"
    )

    # ---- Cost centre allocation -------------------------------------- #
    allocated_to_session = models.ForeignKey(
        "formations.Session",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="expenses",
        verbose_name="Session",
    )
    allocated_to_project = models.ForeignKey(
        "etudes.StudyProject",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="expenses",
        verbose_name="Projet",
    )
    # When neither session nor project is set, the expense is treated as overhead
    is_overhead = models.BooleanField(
        default=False,
        verbose_name="Frais généraux",
        help_text="Cocher si la dépense n'est pas imputable à un service ou projet.",
    )

    # ---- Receipt & justification ------------------------------------- #
    receipt = models.FileField(
        upload_to="receipts/%Y/%m/",
        blank=True,
        verbose_name="Justificatif",
    )
    receipt_missing = models.BooleanField(
        default=False,
        verbose_name="Justificatif manquant",
        help_text="Cocher si le justificatif n'est pas encore disponible.",
    )

    # ---- Approval ---------------------------------------------------- #
    approval_status = models.CharField(
        max_length=20,
        choices=APPROVAL_CHOICES,
        default=APPROVAL_APPROVED,  # Owner approves own entries by default
        verbose_name="Statut d'approbation",
    )
    approval_notes = models.TextField(blank=True, verbose_name="Notes d'approbation")

    notes = models.TextField(blank=True, verbose_name="Notes")

    class Meta:
        verbose_name = "Dépense"
        verbose_name_plural = "Dépenses"
        ordering = ["-date"]
        indexes = [
            models.Index(fields=["date"]),
            models.Index(fields=["approval_status"]),
            models.Index(fields=["category"]),
        ]

    def __str__(self):
        return f"{self.date} — {self.description} ({self.amount} DA)"

    def clean(self):
        filled = sum(
            [
                bool(self.allocated_to_session_id),
                bool(self.allocated_to_project_id),
                bool(self.is_overhead),
            ]
        )
        if filled == 0:
            raise ValidationError(
                "Imputez la dépense à une session, un projet, ou cochez 'Frais généraux'."
            )
        if filled > 1:
            raise ValidationError(
                "Une dépense ne peut être imputée qu'à un seul centre de coût."
            )

    # ---- Convenience properties -------------------------------------- #

    @property
    def cost_centre_label(self):
        """Human-readable cost centre for display."""
        if self.allocated_to_session_id:
            return str(self.allocated_to_session)
        if self.allocated_to_project_id:
            return str(self.allocated_to_project)
        return "Frais généraux"

    @property
    def needs_action(self):
        """True if the expense requires attention (missing receipt or pending approval)."""
        return self.receipt_missing or self.approval_status == self.APPROVAL_PENDING

    @property
    def is_approved(self):
        return self.approval_status == self.APPROVAL_APPROVED


# ======================================================================= #
# Financial period (helper for reporting)
# ======================================================================= #


class FinancialPeriod(TimeStampedModel):
    """
    A named financial period (typically a fiscal year or quarter) used to
    group invoices and expenses for reporting.

    Optional — the reporting app can operate without it by filtering on
    invoice_date ranges, but explicit periods make it easier to lock
    data once a period is closed and prevent retroactive changes.
    """

    PERIOD_YEAR = "year"
    PERIOD_QUARTER = "quarter"
    PERIOD_MONTH = "month"
    PERIOD_CUSTOM = "custom"

    PERIOD_TYPE_CHOICES = [
        (PERIOD_YEAR, "Exercice annuel"),
        (PERIOD_QUARTER, "Trimestre"),
        (PERIOD_MONTH, "Mois"),
        (PERIOD_CUSTOM, "Période personnalisée"),
    ]

    name = models.CharField(
        max_length=100, verbose_name="Nom", help_text="Ex. Exercice 2026, Q1 2026."
    )
    period_type = models.CharField(
        max_length=10, choices=PERIOD_TYPE_CHOICES, default=PERIOD_YEAR
    )
    date_start = models.DateField(verbose_name="Début")
    date_end = models.DateField(verbose_name="Fin")
    is_closed = models.BooleanField(
        default=False,
        verbose_name="Clôturé",
        help_text="Une période clôturée ne devrait plus recevoir de nouvelles écritures.",
    )
    notes = models.TextField(blank=True, verbose_name="Notes")

    class Meta:
        verbose_name = "Période financière"
        verbose_name_plural = "Périodes financières"
        ordering = ["-date_start"]

    def __str__(self):
        return self.name

    # ------------------------------------------------------------------ #
    # Aggregate snapshots for the period
    # ------------------------------------------------------------------ #

    @property
    def total_invoiced_ht(self):
        return Invoice.objects.filter(
            invoice_date__range=[self.date_start, self.date_end],
            status__in=[
                Invoice.STATUS_UNPAID,
                Invoice.STATUS_PARTIALLY_PAID,
                Invoice.STATUS_PAID,
            ],
        ).aggregate(total=Sum("amount_ht"))["total"] or Decimal("0")

    @property
    def total_collected(self):
        """Sum of confirmed payments within the period."""
        return Payment.objects.filter(
            date__range=[self.date_start, self.date_end],
            status=Payment.STATUS_CONFIRMED,
        ).aggregate(total=Sum("amount"))["total"] or Decimal("0")

    @property
    def total_expenses(self):
        return Expense.objects.filter(
            date__range=[self.date_start, self.date_end],
            approval_status=Expense.APPROVAL_APPROVED,
        ).aggregate(total=Sum("amount"))["total"] or Decimal("0")

    @property
    def gross_margin(self):
        return self.total_invoiced_ht - self.total_expenses

    @property
    def formation_revenue_ht(self):
        return Invoice.objects.filter(
            invoice_date__range=[self.date_start, self.date_end],
            invoice_type=Invoice.TYPE_FORMATION,
            status__in=[
                Invoice.STATUS_UNPAID,
                Invoice.STATUS_PARTIALLY_PAID,
                Invoice.STATUS_PAID,
            ],
        ).aggregate(total=Sum("amount_ht"))["total"] or Decimal("0")

    @property
    def etude_revenue_ht(self):
        return Invoice.objects.filter(
            invoice_date__range=[self.date_start, self.date_end],
            invoice_type=Invoice.TYPE_ETUDE,
            status__in=[
                Invoice.STATUS_UNPAID,
                Invoice.STATUS_PARTIALLY_PAID,
                Invoice.STATUS_PAID,
            ],
        ).aggregate(total=Sum("amount_ht"))["total"] or Decimal("0")
