"""
Clients models.
"""

from django.db import models
from django.db.models import Sum, Q

from core.base_models import TimeStampedModel


class Client(TimeStampedModel):
    """
    Client — may be a company or an individual professional.
    """

    TYPE_COMPANY = "company"
    TYPE_INDIVIDUAL = "individual"

    TYPE_CHOICES = [
        (TYPE_COMPANY, "Entreprise"),
        (TYPE_INDIVIDUAL, "Particulier"),
    ]

    name = models.CharField(max_length=255, verbose_name="Nom")
    client_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default=TYPE_COMPANY,
        verbose_name="Type de client",
    )

    # ---- Contact information ----------------------------------------- #
    address = models.TextField(blank=True, verbose_name="Adresse")
    postal_code = models.CharField(
        max_length=10, blank=True, verbose_name="Code postal"
    )
    city = models.CharField(max_length=100, blank=True, verbose_name="Ville")
    phone = models.CharField(max_length=50, blank=True, verbose_name="Téléphone")
    email = models.EmailField(blank=True, verbose_name="Email")
    website = models.URLField(blank=True, verbose_name="Site web")

    # ---- Primary contact person (legacy; multi-contact via ClientContact) #
    contact_name = models.CharField(
        max_length=255, blank=True, verbose_name="Nom du contact principal"
    )
    contact_phone = models.CharField(
        max_length=50, blank=True, verbose_name="Téléphone du contact"
    )
    contact_email = models.EmailField(blank=True, verbose_name="Email du contact")

    # ---- Algerian registration numbers ------------------------------- #
    registration_number = models.CharField(
        max_length=100, blank=True, verbose_name="Numéro RC"
    )
    nif = models.CharField(max_length=100, blank=True, verbose_name="NIF")
    nis = models.CharField(max_length=100, blank=True, verbose_name="NIS")

    # ---- Sector & notes ---------------------------------------------- #
    activity_sector = models.CharField(
        max_length=255, blank=True, verbose_name="Secteur d'activité"
    )
    notes = models.TextField(blank=True, verbose_name="Notes")

    # ---- Status ------------------------------------------------------- #
    is_active = models.BooleanField(
        default=True,
        verbose_name="Actif",
        help_text="Désactiver plutôt que supprimer un client ayant un historique.",
    )

    class Meta:
        verbose_name = "Client"
        verbose_name_plural = "Clients"
        ordering = ["name"]

    def __str__(self):
        return self.name

    # ------------------------------------------------------------------ #
    # Financial aggregates — single DB queries, no Python loops
    # ------------------------------------------------------------------ #

    @property
    def outstanding_balance(self):
        """Total amount still owed across all unpaid / partially-paid invoices."""
        from financial.models import Invoice

        result = Invoice.objects.filter(
            client=self,
            status__in=[Invoice.STATUS_UNPAID, Invoice.STATUS_PARTIALLY_PAID],
        ).aggregate(total=Sum("amount_remaining"))
        return result["total"] or 0

    @property
    def total_revenue(self):
        """Total TTC collected from this client (fully paid invoices only)."""
        from financial.models import Invoice

        result = Invoice.objects.filter(
            client=self, status=Invoice.STATUS_PAID
        ).aggregate(total=Sum("amount_ttc"))
        return result["total"] or 0

    @property
    def invoice_count(self):
        from financial.models import Invoice

        return Invoice.objects.filter(client=self).count()

    @property
    def has_outstanding_balance(self):
        return self.outstanding_balance > 0


class ClientContact(TimeStampedModel):
    """
    Additional contact persons for a client company.
    Allows storing multiple named contacts (e.g. purchasing director,
    technical manager, accountant) under one client record.
    """

    client = models.ForeignKey(
        Client, on_delete=models.CASCADE, related_name="contacts", verbose_name="Client"
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
        ordering = ["-is_primary", "last_name"]

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.client.name})"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    def save(self, *args, **kwargs):
        """Enforce at-most-one primary contact per client."""
        if self.is_primary:
            ClientContact.objects.filter(client=self.client, is_primary=True).exclude(
                pk=self.pk
            ).update(is_primary=False)
        super().save(*args, **kwargs)
