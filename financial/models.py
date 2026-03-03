"""
Financial models — v3.0
Invoices (3-stage lifecycle: proforma → BC → finale), line items with flexible
pricing modes, payments, credit notes, expenses.

Key changes from v2.x
─────────────────────
* Invoice now has a `phase` (PROFORMA / FINALE) that drives all business logic.
* `proforma_reference`  — sequential PF-F/E-YYYY-NNN, assigned at creation.
* `reference`           — sequential F/E-YYYY-NNN, assigned only at finalization.
* Bon de Commande fields added; BC number required to unlock finalization.
* `amount_in_words` stored for mandatory printed mention.
* InvoiceItem replaces quantity/unit with `pricing_mode` + `nb_persons` + `nb_days`;
  total_ht formula varies per mode (see PricingMode docstring).
* TVA default corrected to 9% for formations (Algerian fiscal code).
* Payment.clean() guards phase=FINALE.
* All TextChoices used throughout.
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
    A proforma or final tax invoice issued to a client.

    Lifecycle
    ---------
    PROFORMA phase
        status = draft  → (mark as sent) → sent
        Once a Bon de Commande number is recorded, the proforma may be finalized.

    FINALE phase
        status = unpaid → partially_paid → paid
               unpaid   → voided
               paid     → [issue CreditNote; cannot void directly]

    Sequential numbers
        proforma_reference  PF-F-{YEAR}-{NNN} / PF-E-{YEAR}-{NNN}  — set on create
        reference           F-{YEAR}-{NNN}    / E-{YEAR}-{NNN}      — set on finalize

    Business rules enforced here
        * Line items cannot be edited after finalization (enforced in item.save()).
        * TVA rate is snapshotted; auto-set to 0 when client.is_tva_exempt is True.
        * amount_paid / amount_remaining are denormalized columns kept in sync by
          Payment.save() / delete() so Client aggregate queries need no joins.
    """

    class InvoiceType(models.TextChoices):
        FORMATION = "formation", "Formation"
        ETUDE = "etude", "Étude"

    class Phase(models.TextChoices):
        PROFORMA = "proforma", "Facture Proforma"
        FINALE = "finale", "Facture Finale"

    class Status(models.TextChoices):
        # Proforma statuses
        DRAFT = "draft", "Brouillon"
        SENT = "sent", "Envoyée au client"
        # Finale statuses
        UNPAID = "unpaid", "Non payée"
        PARTIALLY_PAID = "partially_paid", "Partiellement payée"
        PAID = "paid", "Payée"
        VOIDED = "voided", "Annulée"
        CREDIT_NOTE = "credit_note", "Avoir émis"

    # ---- Identity ---------------------------------------------------- #
    invoice_type = models.CharField(
        max_length=20,
        choices=InvoiceType.choices,
        verbose_name="Type",
        db_index=True,
    )
    phase = models.CharField(
        max_length=10,
        choices=Phase.choices,
        default=Phase.PROFORMA,
        verbose_name="Phase",
        db_index=True,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        verbose_name="Statut",
        db_index=True,
    )

    # ---- References -------------------------------------------------- #
    # proforma_reference: PF-F-2026-001 — generated at creation
    proforma_reference = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="N° Proforma",
        help_text="Généré automatiquement à la création.",
    )
    # reference: F-2026-001 — generated at finalization, null until then
    reference = models.CharField(
        max_length=50,
        unique=True,
        null=True,
        blank=True,
        verbose_name="N° Facture finale",
        help_text="Généré automatiquement à la finalisation — séquence indépendante.",
    )
    # Optional internal ref visible on printed doc header
    page_ref = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Réf. interne (en-tête)",
        help_text="Ex. GSCOM — affiché en haut à droite du document imprimé.",
    )

    # ---- Parties ----------------------------------------------------- #
    client = models.ForeignKey(
        Client,
        on_delete=models.PROTECT,
        related_name="invoices",
        verbose_name="Client",
    )
    session = models.ForeignKey(
        "formations.Session",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invoices",
        verbose_name="Session (traçabilité)",
    )
    study_project = models.ForeignKey(
        "etudes.StudyProject",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invoices",
        verbose_name="Projet d'étude (traçabilité)",
    )

    # ---- Client snapshot — frozen at finalization -------------------- #
    # Stored so that editing the client record cannot alter printed invoices.
    client_name_snapshot = models.CharField(
        max_length=255, blank=True, verbose_name="Nom client (snapshot)"
    )
    client_address_snapshot = models.TextField(
        blank=True, verbose_name="Adresse client (snapshot)"
    )
    client_type_snapshot = models.CharField(
        max_length=20, blank=True, verbose_name="Type client (snapshot)"
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
    client_ai_snapshot = models.CharField(
        max_length=100, blank=True, verbose_name="A.I. client (snapshot)"
    )
    client_nin_snapshot = models.CharField(
        max_length=20, blank=True, verbose_name="NIN client (snapshot)"
    )
    client_rib_snapshot = models.CharField(
        max_length=255, blank=True, verbose_name="RIB client (snapshot)"
    )

    # ---- Dates ------------------------------------------------------- #
    invoice_date = models.DateField(
        verbose_name="Date d'émission",
        help_text="Date de la proforma; conservée sur la finale.",
    )
    validity_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Date de validité (proforma)",
        help_text="Défaut : 30 jours après la date d'émission.",
    )
    due_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Date d'échéance (finale)",
    )
    finalized_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Date de finalisation",
    )

    # ---- Bon de Commande --------------------------------------------- #
    bon_commande_number = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="N° Bon de Commande client",
        help_text="Requis pour finaliser la facture.",
    )
    bon_commande_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Date du BC",
    )
    bon_commande_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Montant BC (vérification)",
        help_text="Optionnel — pour cross-check avec le montant de la facture.",
    )
    bon_commande_scan = models.FileField(
        upload_to="bons_commande/%Y/%m/",
        blank=True,
        verbose_name="Scan BC (optionnel)",
    )

    # ---- Amounts (DA) ------------------------------------------------ #
    amount_ht = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name="Montant HT (DA)",
    )
    tva_rate = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        default=Decimal("0.09"),
        verbose_name="Taux TVA",
        help_text="9% pour les formations ; 19% pour les études. 0 si client exonéré.",
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
    # Denormalized — maintained by Payment.save() / delete()
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
    # Auto-generated: "Cent Neuf Mille Dinars Algériens" — mandatory on printed invoice
    amount_in_words = models.CharField(
        max_length=500,
        blank=True,
        verbose_name="Montant en lettres",
        help_text="Généré automatiquement lors de la finalisation.",
    )

    # ---- Notes & footer ---------------------------------------------- #
    notes = models.TextField(blank=True, verbose_name="Notes internes")
    footer_text = models.TextField(
        blank=True,
        verbose_name="Pied de page (personnalisé)",
        help_text="Conditions de paiement, RIB, etc. Écrase le pied de page par défaut.",
    )

    class Meta:
        verbose_name = "Facture"
        verbose_name_plural = "Factures"
        ordering = ["-invoice_date", "-proforma_reference"]
        indexes = [
            models.Index(fields=["phase", "status"]),
            models.Index(fields=["client", "phase", "status"]),
            models.Index(fields=["invoice_type", "invoice_date"]),
        ]

    def __str__(self):
        ref = self.reference or self.proforma_reference
        return f"{ref} — {self.client.name}"

    # ------------------------------------------------------------------ #
    # Reference generation
    # ------------------------------------------------------------------ #

    @classmethod
    def _next_proforma_reference(cls, invoice_type: str, year: int) -> str:
        """PF-F-YYYY-NNN / PF-E-YYYY-NNN — independent sequence."""
        from core.models import BureauEtudeInfo, FormationInfo

        if invoice_type == cls.InvoiceType.FORMATION:
            prefix = FormationInfo.get_instance().proforma_prefix or "PF-F"
        else:
            prefix = BureauEtudeInfo.get_instance().proforma_prefix or "PF-E"

        with transaction.atomic():
            count = (
                cls.objects.select_for_update()
                .filter(invoice_type=invoice_type, invoice_date__year=year)
                .count()
            ) + 1
        return f"{prefix}-{year}-{count:03d}"

    @classmethod
    def _next_final_reference(cls, invoice_type: str, year: int) -> str:
        """F-YYYY-NNN / E-YYYY-NNN — independent sequence, gapless."""
        from core.models import BureauEtudeInfo, FormationInfo

        if invoice_type == cls.InvoiceType.FORMATION:
            prefix = FormationInfo.get_instance().invoice_prefix or "F"
        else:
            prefix = BureauEtudeInfo.get_instance().invoice_prefix or "E"

        with transaction.atomic():
            count = (
                cls.objects.select_for_update()
                .filter(
                    invoice_type=invoice_type,
                    phase=cls.Phase.FINALE,
                    finalized_at__year=year,
                )
                .count()
            ) + 1
        return f"{prefix}-{year}-{count:03d}"

    # ------------------------------------------------------------------ #
    # Finalization
    # ------------------------------------------------------------------ #

    def finalize(self, amount_in_words: str = "") -> None:
        """
        Promote a proforma to a finalized invoice.

        Validates:
          * BC number is present.
          * Client profile is complete for their type.
          * TVA rate is zeroed for exempt clients.

        Assigns the final sequential reference, snapshots the client record,
        sets status → UNPAID, records finalized_at.
        """
        if self.phase == self.Phase.FINALE:
            raise ValidationError("Cette facture est déjà finalisée.")

        if not self.bon_commande_number:
            raise ValidationError(
                "Impossible de finaliser sans numéro de Bon de Commande."
            )

        missing = self.client.missing_fields_for_invoice()
        if missing:
            raise ValidationError(
                f"Profil client incomplet. Champs manquants : {', '.join(missing)}."
            )

        # Snapshot client fields
        c = self.client
        self.client_name_snapshot = c.name
        self.client_address_snapshot = c.address
        self.client_type_snapshot = c.client_type
        self.client_nif_snapshot = c.nif
        self.client_nis_snapshot = c.nis
        self.client_rc_snapshot = c.rc
        self.client_ai_snapshot = c.article_imposition
        self.client_nin_snapshot = c.nin
        self.client_rib_snapshot = c.rib

        # Apply TVA exemption
        if c.is_tva_exempt:
            self.tva_rate = Decimal("0.00")
            self.amount_tva = Decimal("0.00")
            self.amount_ttc = self.amount_ht

        # Assign final reference
        year = timezone.now().year
        self.reference = self._next_final_reference(self.invoice_type, year)

        # Promote phase
        self.phase = self.Phase.FINALE
        self.status = self.Status.UNPAID
        self.finalized_at = timezone.now()
        self.amount_remaining = self.amount_ttc
        if amount_in_words:
            self.amount_in_words = amount_in_words

        self.save()

    # ------------------------------------------------------------------ #
    # Amount calculation
    # ------------------------------------------------------------------ #

    def recalculate_amounts(self) -> None:
        """
        Recompute totals from line items.
        Called by InvoiceItem.save() and InvoiceItem.delete().
        No-op on finalized invoices (line items are locked).
        """
        if self.phase == self.Phase.FINALE:
            return  # Lock: do not mutate finalized amounts

        total_ht = self.items.aggregate(total=Sum("total_ht"))["total"] or Decimal("0")
        self.amount_ht = total_ht
        self.amount_tva = (total_ht * self.tva_rate).quantize(Decimal("0.01"))
        self.amount_ttc = self.amount_ht + self.amount_tva
        self.amount_remaining = self.amount_ttc - self.amount_paid
        self.save(
            update_fields=["amount_ht", "amount_tva", "amount_ttc", "amount_remaining"]
        )

    def refresh_payment_totals(self) -> None:
        """
        Recompute amount_paid / amount_remaining from confirmed payments.
        Called by Payment.save() and Payment.delete().
        """
        paid = self.payments.filter(status=Payment.Status.CONFIRMED).aggregate(
            total=Sum("amount")
        )["total"] or Decimal("0")
        self.amount_paid = paid
        self.amount_remaining = max(self.amount_ttc - paid, Decimal("0"))

        # Update status (only for finale invoices)
        if self.phase == self.Phase.FINALE and self.status not in [
            self.Status.VOIDED,
            self.Status.CREDIT_NOTE,
        ]:
            if self.amount_remaining <= 0:
                self.status = self.Status.PAID
            elif self.amount_paid > 0:
                self.status = self.Status.PARTIALLY_PAID
            else:
                self.status = self.Status.UNPAID

        self.save(update_fields=["amount_paid", "amount_remaining", "status"])

    # ------------------------------------------------------------------ #
    # Save
    # ------------------------------------------------------------------ #

    def save(self, *args, **kwargs):
        if not self.pk:
            # Auto-generate proforma reference on first save
            if not self.proforma_reference:
                year = (self.invoice_date or timezone.now().date()).year
                self.proforma_reference = self._next_proforma_reference(
                    self.invoice_type, year
                )
            # Default validity: +30 days
            if not self.validity_date and self.invoice_date:
                from datetime import timedelta

                self.validity_date = self.invoice_date + timedelta(days=30)

        super().save(*args, **kwargs)

    # ------------------------------------------------------------------ #
    # Status helpers
    # ------------------------------------------------------------------ #

    @property
    def is_locked(self) -> bool:
        """True when the invoice is finalized — line items cannot be changed."""
        return self.phase == self.Phase.FINALE

    @property
    def is_payable(self) -> bool:
        return self.phase == self.Phase.FINALE and self.status in [
            self.Status.UNPAID,
            self.Status.PARTIALLY_PAID,
        ]

    @property
    def has_bon_commande(self) -> bool:
        return bool(self.bon_commande_number)

    @property
    def can_be_finalized(self) -> bool:
        return (
            self.phase == self.Phase.PROFORMA
            and self.has_bon_commande
            and self.client.is_invoice_ready
        )

    @property
    def is_overdue(self) -> bool:
        return (
            self.due_date
            and self.due_date < timezone.now().date()
            and self.status in [self.Status.UNPAID, self.Status.PARTIALLY_PAID]
        )

    @property
    def days_overdue(self) -> int:
        if not self.is_overdue:
            return 0
        return (timezone.now().date() - self.due_date).days

    @property
    def payment_completion_percent(self) -> float:
        if not self.amount_ttc:
            return 0.0
        return round(float(self.amount_paid / self.amount_ttc) * 100, 1)

    def void(self, reason: str = "") -> None:
        """
        Mark a finalized invoice as voided.
        The invoice retains its sequential number (gapless requirement).
        Cannot void a fully-paid invoice — issue a credit note instead.
        """
        if self.phase != self.Phase.FINALE:
            raise ValidationError("Seule une facture finale peut être annulée.")
        if self.status == self.Status.PAID:
            raise ValidationError(
                "Impossible d'annuler une facture déjà payée. Émettez un avoir."
            )
        self.status = self.Status.VOIDED
        if reason:
            self.notes = f"[ANNULÉ] {reason}\n\n{self.notes}".strip()
        self.save(update_fields=["status", "notes"])


# ======================================================================= #
# Invoice line items
# ======================================================================= #


class InvoiceItem(TimeStampedModel):
    """
    A single line on an invoice.

    PricingMode determines how total_ht is computed:

        per_person           → unit_price_ht × nb_persons
        per_day              → unit_price_ht × nb_days
        per_person_per_day   → unit_price_ht × nb_persons × nb_days
        forfait              → unit_price_ht (fixed, nb_persons=nb_days=1)

    An optional line-level discount_percent is applied after the base
    calculation before rounding.

    Editing is blocked when the parent invoice is finalized (phase=FINALE).
    """

    class PricingMode(models.TextChoices):
        PER_PERSON = "per_person", "Par personne"
        PER_DAY = "per_day", "Par jour"
        PER_PERSON_PER_DAY = "per_person_per_day", "Par personne × par jour"
        FORFAIT = "forfait", "Forfait"

    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name="Facture",
    )
    order = models.PositiveIntegerField(default=1, verbose_name="Ordre")
    description = models.CharField(
        max_length=500,
        verbose_name="Désignation",
        help_text="Titre de la formation ou du livrable d'étude.",
    )

    # ---- Pricing mode ------------------------------------------------ #
    pricing_mode = models.CharField(
        max_length=20,
        choices=PricingMode.choices,
        default=PricingMode.PER_PERSON,
        verbose_name="Mode de tarification",
    )
    nb_persons = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal("1.00"),
        verbose_name="Nombre de personnes",
        help_text="Utilisé pour per_person et per_person_per_day.",
    )
    nb_days = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal("1.00"),
        verbose_name="Nombre de jours",
        help_text="Utilisé pour per_day et per_person_per_day.",
    )
    unit_price_ht = models.DecimalField(
        max_digits=14, decimal_places=2, verbose_name="Prix unitaire HT (DA)"
    )
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
        help_text="Calculé automatiquement selon le mode de tarification.",
    )

    class Meta:
        verbose_name = "Ligne de facture"
        verbose_name_plural = "Lignes de facture"
        ordering = ["invoice", "order"]

    def __str__(self):
        return f"{self.invoice.proforma_reference} — {self.description}"

    def _compute_total_ht(self) -> Decimal:
        mode = self.pricing_mode
        if mode == self.PricingMode.PER_PERSON:
            base = self.unit_price_ht * self.nb_persons
        elif mode == self.PricingMode.PER_DAY:
            base = self.unit_price_ht * self.nb_days
        elif mode == self.PricingMode.PER_PERSON_PER_DAY:
            base = self.unit_price_ht * self.nb_persons * self.nb_days
        else:  # forfait
            base = self.unit_price_ht
        discount = base * (self.discount_percent / Decimal("100"))
        return (base - discount).quantize(Decimal("0.01"))

    def save(self, *args, **kwargs):
        if self.invoice.is_locked:
            raise ValidationError(
                "Les lignes d'une facture finalisée ne peuvent pas être modifiées. "
                "Émettez un avoir si nécessaire."
            )
        self.total_ht = self._compute_total_ht()
        super().save(*args, **kwargs)
        self.invoice.recalculate_amounts()

    def delete(self, *args, **kwargs):
        if self.invoice.is_locked:
            raise ValidationError(
                "Les lignes d'une facture finalisée ne peuvent pas être supprimées."
            )
        invoice = self.invoice
        super().delete(*args, **kwargs)
        invoice.recalculate_amounts()


# ======================================================================= #
# Payments
# ======================================================================= #


class Payment(TimeStampedModel):
    """
    A single payment instalment against a finalized invoice.
    Multiple Payment records per Invoice are allowed (partial payments).

    Payments are only accepted on invoices with phase=FINALE and status in
    [unpaid, partially_paid].
    """

    class Method(models.TextChoices):
        VIREMENT = "virement", "Virement bancaire"
        CHEQUE = "cheque", "Chèque"
        ESPECES = "especes", "Espèces"
        OTHER = "autre", "Autre"

    class Status(models.TextChoices):
        PENDING = "pending", "En attente de confirmation"
        CONFIRMED = "confirmed", "Confirmé"
        REVERSED = "reversed", "Annulé / retourné"

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
        max_length=10,
        choices=Method.choices,
        default=Method.VIREMENT,
        verbose_name="Mode de paiement",
    )
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.CONFIRMED,
        verbose_name="Statut",
    )
    reference = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Référence",
        help_text="N° virement, n° chèque, etc.",
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

        # Phase guard — payments only on finalized invoices
        if self.invoice.phase != Invoice.Phase.FINALE:
            raise ValidationError(
                "Les paiements ne sont acceptés que sur les factures finalisées."
            )

        if self.pk is None and not self.invoice.is_payable:
            raise ValidationError(
                f"La facture {self.invoice.reference} n'est pas en attente de paiement."
            )

        if self.amount and self.amount <= 0:
            raise ValidationError("Le montant doit être positif.")

        # Overpayment guard
        already_paid = self.invoice.amount_paid
        if self.pk:
            existing_amount = (
                Payment.objects.filter(pk=self.pk)
                .values_list("amount", flat=True)
                .first()
                or 0
            )
            already_paid -= Decimal(str(existing_amount))

        if self.amount and (already_paid + self.amount) > self.invoice.amount_ttc:
            raise ValidationError(
                f"Ce paiement ({self.amount} DA) dépasserait le montant total "
                f"de la facture ({self.invoice.amount_ttc} DA)."
            )

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.invoice.refresh_payment_totals()

    def delete(self, *args, **kwargs):
        invoice = self.invoice
        super().delete(*args, **kwargs)
        invoice.refresh_payment_totals()

    @property
    def is_confirmed(self) -> bool:
        return self.status == self.Status.CONFIRMED


# ======================================================================= #
# Credit notes
# ======================================================================= #


class CreditNote(TimeStampedModel):
    """
    A credit note (avoir) that partially or fully reverses a finalized invoice.

    CreditNote is a separate document referencing the original invoice.
    When is_full_reversal is True, the original invoice's status is set to
    STATUS_CREDIT_NOTE.
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
        verbose_name="N° Avoir",
        help_text="Généré automatiquement — ex. AV-2026-001.",
    )
    date = models.DateField(verbose_name="Date")
    reason = models.TextField(verbose_name="Motif")
    amount_ht = models.DecimalField(
        max_digits=14, decimal_places=2, verbose_name="Montant HT (DA)"
    )
    tva_rate = models.DecimalField(
        max_digits=5, decimal_places=4, default=Decimal("0.09"), verbose_name="Taux TVA"
    )
    amount_tva = models.DecimalField(
        max_digits=14, decimal_places=2, verbose_name="Montant TVA (DA)"
    )
    amount_ttc = models.DecimalField(
        max_digits=14, decimal_places=2, verbose_name="Montant TTC (DA)"
    )
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
    def _next_reference(cls, year: int) -> str:
        with transaction.atomic():
            count = (
                cls.objects.select_for_update().filter(date__year=year).count()
            ) + 1
        return f"AV-{year}-{count:03d}"

    def save(self, *args, **kwargs):
        if not self.reference:
            year = (self.date or timezone.now().date()).year
            self.reference = self._next_reference(year)
        self.amount_tva = (self.amount_ht * self.tva_rate).quantize(Decimal("0.01"))
        self.amount_ttc = self.amount_ht + self.amount_tva
        super().save(*args, **kwargs)
        if self.is_full_reversal:
            Invoice.objects.filter(pk=self.original_invoice_id).update(
                status=Invoice.Status.CREDIT_NOTE
            )

    @property
    def coverage_percent(self) -> float:
        if not self.original_invoice.amount_ttc:
            return 0.0
        return round(float(self.amount_ttc / self.original_invoice.amount_ttc) * 100, 1)


# ======================================================================= #
# Expenses
# ======================================================================= #


class ExpenseCategory(TimeStampedModel):
    """
    Configurable expense category. Pre-seeded with spec-defined presets;
    the owner can add more.
    """

    name = models.CharField(max_length=100, unique=True, verbose_name="Catégorie")
    description = models.TextField(blank=True, verbose_name="Description")
    is_direct_cost = models.BooleanField(
        default=True,
        verbose_name="Coût direct",
        help_text="Coût direct = imputable à un service ou projet. Indirect = frais généraux.",
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

    Allocation model — mutually exclusive cost centres:
        allocated_to_session    → direct cost for a training session
        allocated_to_project    → direct cost for a consulting project
        is_overhead = True      → general overhead (frais généraux)

    clean() enforces exactly one cost centre per expense.
    """

    class ApprovalStatus(models.TextChoices):
        PENDING = "pending", "En attente"
        APPROVED = "approved", "Approuvée"
        REJECTED = "rejected", "Refusée"

    # ---- Core -------------------------------------------------------- #
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
    supplier = models.CharField(
        max_length=255, blank=True, verbose_name="Fournisseur / bénéficiaire"
    )
    payment_reference = models.CharField(
        max_length=100, blank=True, verbose_name="Référence de paiement"
    )

    # ---- Cost centre ------------------------------------------------- #
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
    is_overhead = models.BooleanField(
        default=False,
        verbose_name="Frais généraux",
        help_text="Cocher si non imputable à un service ou projet.",
    )

    # ---- Receipt & approval ------------------------------------------ #
    receipt = models.FileField(
        upload_to="receipts/%Y/%m/", blank=True, verbose_name="Justificatif"
    )
    receipt_missing = models.BooleanField(
        default=False, verbose_name="Justificatif manquant"
    )
    approval_status = models.CharField(
        max_length=10,
        choices=ApprovalStatus.choices,
        default=ApprovalStatus.APPROVED,
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

    @property
    def cost_centre_label(self) -> str:
        if self.allocated_to_session_id:
            return str(self.allocated_to_session)
        if self.allocated_to_project_id:
            return str(self.allocated_to_project)
        return "Frais généraux"

    @property
    def needs_action(self) -> bool:
        return (
            self.receipt_missing or self.approval_status == self.ApprovalStatus.PENDING
        )

    @property
    def is_approved(self) -> bool:
        return self.approval_status == self.ApprovalStatus.APPROVED


# ======================================================================= #
# Financial period (reporting helper)
# ======================================================================= #


class FinancialPeriod(TimeStampedModel):
    """
    A named financial period used to group finalized invoices and expenses
    for reporting.  Optional — the reporting app can filter on invoice_date
    ranges directly, but explicit periods simplify period-close workflows.
    """

    class PeriodType(models.TextChoices):
        YEAR = "year", "Exercice annuel"
        QUARTER = "quarter", "Trimestre"
        MONTH = "month", "Mois"
        CUSTOM = "custom", "Période personnalisée"

    name = models.CharField(
        max_length=100, verbose_name="Nom", help_text="Ex. Exercice 2026."
    )
    period_type = models.CharField(
        max_length=10, choices=PeriodType.choices, default=PeriodType.YEAR
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
        constraints = [
            models.CheckConstraint(
                condition=models.Q(date_end__gte=models.F("date_start")),
                name="financial_period_end_after_start",
            )
        ]

    def __str__(self):
        return self.name

    # ---- Aggregates — all scoped to FINALE invoices only ------------- #

    def _invoice_qs(self):
        return Invoice.objects.filter(
            phase=Invoice.Phase.FINALE,
            invoice_date__range=[self.date_start, self.date_end],
            status__in=[
                Invoice.Status.UNPAID,
                Invoice.Status.PARTIALLY_PAID,
                Invoice.Status.PAID,
            ],
        )

    @property
    def total_invoiced_ht(self) -> Decimal:
        return self._invoice_qs().aggregate(t=Sum("amount_ht"))["t"] or Decimal("0")

    @property
    def total_collected(self) -> Decimal:
        return Payment.objects.filter(
            date__range=[self.date_start, self.date_end],
            status=Payment.Status.CONFIRMED,
        ).aggregate(t=Sum("amount"))["t"] or Decimal("0")

    @property
    def total_expenses(self) -> Decimal:
        return Expense.objects.filter(
            date__range=[self.date_start, self.date_end],
            approval_status=Expense.ApprovalStatus.APPROVED,
        ).aggregate(t=Sum("amount"))["t"] or Decimal("0")

    @property
    def gross_margin(self) -> Decimal:
        return self.total_invoiced_ht - self.total_expenses

    @property
    def formation_revenue_ht(self) -> Decimal:
        return self._invoice_qs().filter(
            invoice_type=Invoice.InvoiceType.FORMATION
        ).aggregate(t=Sum("amount_ht"))["t"] or Decimal("0")

    @property
    def etude_revenue_ht(self) -> Decimal:
        return self._invoice_qs().filter(
            invoice_type=Invoice.InvoiceType.ETUDE
        ).aggregate(t=Sum("amount_ht"))["t"] or Decimal("0")
