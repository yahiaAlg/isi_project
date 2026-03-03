"""
Clients models — v3.0
Four distinct legal client profiles aligned with Algerian fiscal requirements.
"""

from django.db import models
from django.db.models import Sum

from core.base_models import TimeStampedModel


class Client(TimeStampedModel):
    """
    Client record supporting four legal profiles:
      PARTICULIER       — private individual (NIN, no TVA)
      AUTO_ENTREPRENEUR — IFU regime (NIF + carte AE, no TVA)
      ENTREPRISE        — legal entity (RC, NIF, NIS, AI, TVA)
      STARTUP           — label startup (inherits ENTREPRISE + label fields)

    The `is_tva_exempt` flag is auto-derived from client_type on save but can
    be overridden for edge cases (e.g. a company with a TVA exemption certificate).
    """

    class ClientType(models.TextChoices):
        PARTICULIER = "particulier", "Particulier"
        AUTO_ENTREPRENEUR = "auto_entrepreneur", "Auto-Entrepreneur"
        ENTREPRISE = "entreprise", "Entreprise"
        STARTUP = "startup", "Startup"

    # ------------------------------------------------------------------ #
    # Identity
    # ------------------------------------------------------------------ #

    client_type = models.CharField(
        max_length=20,
        choices=ClientType.choices,
        default=ClientType.ENTREPRISE,
        verbose_name="Type de client",
        db_index=True,
    )
    name = models.CharField(
        max_length=255,
        verbose_name="Nom / Raison sociale",
        help_text="Raison sociale pour une entreprise, Nom Prénom pour un particulier.",
    )
    forme_juridique = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Forme juridique",
        help_text="SARL / EURL / SPA / SNCI / … — entreprise et startup seulement.",
    )

    # ------------------------------------------------------------------ #
    # Contact
    # ------------------------------------------------------------------ #

    address = models.TextField(blank=True, verbose_name="Adresse")
    postal_code = models.CharField(
        max_length=10, blank=True, verbose_name="Code postal"
    )
    city = models.CharField(max_length=100, blank=True, verbose_name="Ville")
    phone = models.CharField(max_length=50, blank=True, verbose_name="Téléphone")
    email = models.EmailField(blank=True, verbose_name="Email")
    website = models.URLField(blank=True, verbose_name="Site web")
    activity_sector = models.CharField(
        max_length=255, blank=True, verbose_name="Secteur d'activité"
    )

    # ---- Legacy primary contact (multi-contact via ClientContact) ----- #
    contact_name = models.CharField(
        max_length=255, blank=True, verbose_name="Nom du contact principal"
    )
    contact_phone = models.CharField(
        max_length=50, blank=True, verbose_name="Téléphone du contact"
    )
    contact_email = models.EmailField(blank=True, verbose_name="Email du contact")

    # ------------------------------------------------------------------ #
    # Legal / fiscal identifiers
    # Filled according to client_type — validation is enforced at invoice
    # finalization rather than at the model level so partial records are
    # allowed during data entry.
    # ------------------------------------------------------------------ #

    # Particulier only
    nin = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="NIN",
        help_text="Numéro d'Identité Nationale — 18 chiffres (particulier).",
    )

    # AE, Entreprise, Startup
    nif = models.CharField(max_length=100, blank=True, verbose_name="NIF")
    article_imposition = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Article d'imposition (A.I.)",
        help_text="Numéro d'article d'imposition — AE, entreprise et startup.",
    )

    # Entreprise, Startup
    nis = models.CharField(max_length=100, blank=True, verbose_name="NIS")
    rc = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Numéro RC",
        help_text="Registre de Commerce — ex. 21B 0094443-19/00.",
    )

    # All types (optional)
    rib = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="RIB",
        help_text="Relevé d'Identité Bancaire — optionnel, tous types.",
    )

    # AE only
    carte_auto_entrepreneur = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="N° Carte Auto-Entrepreneur",
        help_text="Numéro délivré par l'ANAE.",
    )

    # Startup only
    label_startup_number = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="N° Label Startup",
    )
    label_startup_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Date d'obtention du label",
    )
    programme_accompagnement = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Programme d'accompagnement",
        help_text="ANIE / NEXUS / … — optionnel.",
    )

    # ------------------------------------------------------------------ #
    # TVA flag
    # ------------------------------------------------------------------ #

    is_tva_exempt = models.BooleanField(
        default=False,
        verbose_name="Exonéré de TVA",
        help_text=(
            "Automatiquement mis à True pour les particuliers et auto-entrepreneurs. "
            "Peut être ajusté manuellement pour des cas spéciaux."
        ),
    )

    # ------------------------------------------------------------------ #
    # Status & notes
    # ------------------------------------------------------------------ #

    is_active = models.BooleanField(default=True, verbose_name="Actif")
    notes = models.TextField(blank=True, verbose_name="Notes")

    class Meta:
        verbose_name = "Client"
        verbose_name_plural = "Clients"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["client_type"]),
            models.Index(fields=["is_active", "name"]),
        ]

    def __str__(self):
        return self.name

    # ------------------------------------------------------------------ #
    # Save — auto-derive TVA exemption from client type
    # ------------------------------------------------------------------ #

    def save(self, *args, **kwargs):
        tva_exempt_types = {
            self.ClientType.PARTICULIER,
            self.ClientType.AUTO_ENTREPRENEUR,
        }
        # Only auto-set if the caller hasn't explicitly overridden the field.
        # We always sync for the standard types to avoid stale data.
        if self.client_type in tva_exempt_types:
            self.is_tva_exempt = True
        elif self.client_type in {self.ClientType.ENTREPRISE, self.ClientType.STARTUP}:
            # Keep manually-set override; default False for new records.
            if not self.pk:
                self.is_tva_exempt = False
        super().save(*args, **kwargs)

    # ------------------------------------------------------------------ #
    # Completeness check — used by invoice finalization view
    # ------------------------------------------------------------------ #

    def missing_fields_for_invoice(self) -> list[str]:
        """
        Return a list of human-readable field names that are required for
        invoice finalization but not yet filled.  Empty list means the
        client profile is complete.
        """
        missing: list[str] = []
        t = self.client_type

        required: list[tuple[str, str]] = [
            ("address", "Adresse"),
            ("phone", "Téléphone"),
        ]

        if t == self.ClientType.PARTICULIER:
            required += [("nin", "NIN")]

        elif t == self.ClientType.AUTO_ENTREPRENEUR:
            required += [
                ("nif", "NIF"),
                ("article_imposition", "Article d'imposition"),
                ("carte_auto_entrepreneur", "N° Carte Auto-Entrepreneur"),
            ]

        elif t in {self.ClientType.ENTREPRISE, self.ClientType.STARTUP}:
            required += [
                ("forme_juridique", "Forme juridique"),
                ("rc", "Numéro RC"),
                ("nif", "NIF"),
                ("nis", "NIS"),
                ("article_imposition", "Article d'imposition"),
            ]
            if t == self.ClientType.STARTUP:
                required += [("label_startup_number", "N° Label Startup")]

        for field, label in required:
            if not getattr(self, field, None):
                missing.append(label)

        return missing

    @property
    def is_invoice_ready(self) -> bool:
        """True when all mandatory fields for invoice finalization are present."""
        return len(self.missing_fields_for_invoice()) == 0

    # ------------------------------------------------------------------ #
    # Financial aggregates — single DB queries
    # ------------------------------------------------------------------ #

    @property
    def outstanding_balance(self):
        """Total remaining on unpaid / partially-paid *finalized* invoices."""
        from financial.models import Invoice

        result = Invoice.objects.filter(
            client=self,
            phase=Invoice.Phase.FINALE,
            status__in=[Invoice.Status.UNPAID, Invoice.Status.PARTIALLY_PAID],
        ).aggregate(total=Sum("amount_remaining"))
        return result["total"] or 0

    @property
    def total_revenue(self):
        """Total TTC collected (fully paid finalized invoices)."""
        from financial.models import Invoice

        result = Invoice.objects.filter(
            client=self,
            phase=Invoice.Phase.FINALE,
            status=Invoice.Status.PAID,
        ).aggregate(total=Sum("amount_ttc"))
        return result["total"] or 0

    @property
    def invoice_count(self):
        from financial.models import Invoice

        return Invoice.objects.filter(client=self, phase=Invoice.Phase.FINALE).count()

    @property
    def has_outstanding_balance(self):
        return self.outstanding_balance > 0


class ClientContact(TimeStampedModel):
    """
    Additional contact persons attached to a client record.
    Allows multiple named contacts (purchasing director, accountant, etc.)
    with at-most-one primary contact enforced by save().
    """

    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name="contacts",
        verbose_name="Client",
    )
    first_name = models.CharField(max_length=100, verbose_name="Prénom")
    last_name = models.CharField(max_length=100, verbose_name="Nom")
    job_title = models.CharField(max_length=255, blank=True, verbose_name="Fonction")
    phone = models.CharField(max_length=50, blank=True, verbose_name="Téléphone")
    email = models.EmailField(blank=True, verbose_name="Email")
    is_primary = models.BooleanField(
        default=False,
        verbose_name="Contact principal",
        help_text="Un seul contact principal par client.",
    )
    notes = models.TextField(blank=True, verbose_name="Notes")

    class Meta:
        verbose_name = "Contact client"
        verbose_name_plural = "Contacts clients"
        ordering = ["-is_primary", "last_name", "first_name"]

    def __str__(self):
        return f"{self.full_name} ({self.client.name})"

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    def save(self, *args, **kwargs):
        """Enforce at-most-one primary contact per client."""
        if self.is_primary:
            ClientContact.objects.filter(client=self.client, is_primary=True).exclude(
                pk=self.pk
            ).update(is_primary=False)
        super().save(*args, **kwargs)
