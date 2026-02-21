"""
Formations models — Training catalog, sessions, enrollments, attestations.
"""

from django.db import models, transaction
from django.db.models import Count, Sum
from django.utils import timezone
from datetime import timedelta

from clients.models import Client
from core.base_models import TimeStampedModel


class FormationCategory(TimeStampedModel):
    """
    Thematic category for organizing the training catalog.
    Examples: Sécurité incendie, Travaux en hauteur, Risques chimiques, SST.
    """

    name = models.CharField(max_length=255, unique=True, verbose_name="Catégorie")
    description = models.TextField(blank=True, verbose_name="Description")
    color = models.CharField(
        max_length=7,
        default="#3B82F6",
        verbose_name="Couleur (hex)",
        help_text="Couleur d'affichage dans l'interface (ex. #3B82F6).",
    )

    class Meta:
        verbose_name = "Catégorie de formation"
        verbose_name_plural = "Catégories de formation"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Formation(TimeStampedModel):
    """
    Training program in the catalog — defines a reusable type of training.
    """

    category = models.ForeignKey(
        FormationCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="formations",
        verbose_name="Catégorie",
    )
    title = models.CharField(max_length=255, verbose_name="Titre")
    slug = models.SlugField(
        max_length=255,
        unique=True,
        verbose_name="Slug",
        help_text="Identifiant URL-friendly (généré automatiquement).",
    )
    description = models.TextField(blank=True, verbose_name="Description")
    objectives = models.TextField(blank=True, verbose_name="Objectifs pédagogiques")
    target_audience = models.TextField(blank=True, verbose_name="Public cible")
    prerequisites = models.TextField(blank=True, verbose_name="Prérequis")
    duration_days = models.PositiveIntegerField(default=1, verbose_name="Durée (jours)")
    duration_hours = models.PositiveIntegerField(
        default=8, verbose_name="Durée (heures)"
    )
    base_price = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, verbose_name="Prix de base (DA)"
    )
    max_participants = models.PositiveIntegerField(
        default=20, verbose_name="Capacité maximale"
    )
    min_participants = models.PositiveIntegerField(
        default=5, verbose_name="Minimum de participants"
    )
    is_active = models.BooleanField(default=True, verbose_name="Active")

    # Optional accreditation / certification reference
    accreditation_body = models.CharField(
        max_length=255, blank=True, verbose_name="Organisme d'accréditation"
    )
    accreditation_reference = models.CharField(
        max_length=100, blank=True, verbose_name="Référence d'accréditation"
    )

    class Meta:
        verbose_name = "Formation"
        verbose_name_plural = "Formations"
        ordering = ["title"]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            from django.utils.text import slugify

            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    @property
    def session_count(self):
        return self.sessions.count()

    @property
    def total_participants_trained(self):
        """Total participants across all completed sessions."""
        return Participant.objects.filter(
            session__formation=self, session__status=Session.STATUS_COMPLETED
        ).count()


class Session(TimeStampedModel):
    """
    A scheduled instance of a training program.
    """

    STATUS_PLANNED = "planned"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_COMPLETED = "completed"
    STATUS_CANCELLED = "cancelled"

    STATUS_CHOICES = [
        (STATUS_PLANNED, "Planifiée"),
        (STATUS_IN_PROGRESS, "En cours"),
        (STATUS_COMPLETED, "Terminée"),
        (STATUS_CANCELLED, "Annulée"),
    ]

    formation = models.ForeignKey(
        Formation,
        on_delete=models.CASCADE,
        related_name="sessions",
        verbose_name="Formation",
    )
    # Client who commissioned the session (blank = open/inter-company enrollment)
    client = models.ForeignKey(
        Client,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sessions",
        verbose_name="Client",
    )
    date_start = models.DateField(verbose_name="Date de début")
    date_end = models.DateField(verbose_name="Date de fin")

    trainer = models.ForeignKey(
        "resources.Trainer",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sessions",
        verbose_name="Formateur",
    )
    room = models.ForeignKey(
        "resources.TrainingRoom",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sessions",
        verbose_name="Salle",
    )
    external_location = models.CharField(
        max_length=255, blank=True, verbose_name="Lieu externe (si hors-site)"
    )

    capacity = models.PositiveIntegerField(default=20, verbose_name="Capacité")
    # Allows overriding the formation's base price for this specific session
    price_per_participant = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Prix par participant (DA)",
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PLANNED,
        verbose_name="Statut",
    )

    # Internal notes
    notes = models.TextField(blank=True, verbose_name="Notes")
    # Cancellation reason (filled when status → cancelled)
    cancellation_reason = models.TextField(
        blank=True, verbose_name="Motif d'annulation"
    )

    class Meta:
        verbose_name = "Session"
        verbose_name_plural = "Sessions"
        ordering = ["-date_start"]

    def __str__(self):
        return f"{self.formation.title} — {self.date_start}"

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.date_end and self.date_start and self.date_end < self.date_start:
            raise ValidationError(
                "La date de fin doit être postérieure à la date de début."
            )

    # ------------------------------------------------------------------ #
    # Computed properties
    # ------------------------------------------------------------------ #

    @property
    def effective_price(self):
        """Price to use: session override or formation default."""
        return self.price_per_participant or self.formation.base_price

    @property
    def participant_count(self):
        return self.participants.count()

    @property
    def attended_count(self):
        """Participants who were actually present."""
        return self.participants.filter(attended=True).count()

    @property
    def available_spots(self):
        return self.capacity - self.participant_count

    @property
    def is_full(self):
        return self.participant_count >= self.capacity

    @property
    def fill_rate(self):
        """Fill rate as a percentage (0–100)."""
        if self.capacity == 0:
            return 0
        return round((self.participant_count / self.capacity) * 100, 1)

    @property
    def attendance_rate(self):
        """Actual attendance rate among enrolled participants."""
        if self.participant_count == 0:
            return 0
        return round((self.attended_count / self.participant_count) * 100, 1)

    @property
    def can_be_invoiced(self):
        return self.status == self.STATUS_COMPLETED

    @property
    def total_revenue(self):
        """Gross revenue = effective price × attended participants."""
        return self.effective_price * self.attended_count

    @property
    def duration_days(self):
        """Actual number of calendar days."""
        return (self.date_end - self.date_start).days + 1

    @property
    def is_overdue(self):
        """Planned session whose start date has passed without being started."""
        return (
            self.status == self.STATUS_PLANNED
            and self.date_start < timezone.now().date()
        )


class Participant(TimeStampedModel):
    """
    A person enrolled in a training session.
    """

    session = models.ForeignKey(
        Session,
        on_delete=models.CASCADE,
        related_name="participants",
        verbose_name="Session",
    )
    first_name = models.CharField(max_length=100, verbose_name="Prénom")
    last_name = models.CharField(max_length=100, verbose_name="Nom")
    employer = models.CharField(max_length=255, blank=True, verbose_name="Employeur")
    employer_client = models.ForeignKey(
        Client,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="participants",
        verbose_name="Employeur (client enregistré)",
    )
    phone = models.CharField(max_length=50, blank=True, verbose_name="Téléphone")
    email = models.EmailField(blank=True, verbose_name="Email")
    job_title = models.CharField(max_length=255, blank=True, verbose_name="Fonction")
    attended = models.BooleanField(default=True, verbose_name="Présent")
    notes = models.TextField(blank=True, verbose_name="Notes")

    class Meta:
        verbose_name = "Participant"
        verbose_name_plural = "Participants"
        ordering = ["last_name", "first_name"]
        unique_together = ["session", "first_name", "last_name", "email"]

    def __str__(self):
        return self.full_name

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def has_attestation(self):
        return hasattr(self, "attestation")

    @property
    def eligible_for_attestation(self):
        """
        Participant is eligible if they attended and the session is completed.
        Attendance threshold is read from FormationInfo config.
        """
        return self.attended and self.session.status == Session.STATUS_COMPLETED


class Attestation(TimeStampedModel):
    """
    Certification issued to a participant upon successful completion.
    """

    participant = models.OneToOneField(
        Participant,
        on_delete=models.CASCADE,
        related_name="attestation",
        verbose_name="Participant",
    )
    session = models.ForeignKey(
        Session,
        on_delete=models.CASCADE,
        related_name="attestations",
        verbose_name="Session",
    )
    reference = models.CharField(max_length=50, unique=True, verbose_name="Référence")
    issue_date = models.DateField(verbose_name="Date d'émission")
    valid_until = models.DateField(verbose_name="Valide jusqu'au")
    is_issued = models.BooleanField(default=True, verbose_name="Émise")

    class Meta:
        verbose_name = "Attestation"
        verbose_name_plural = "Attestations"
        ordering = ["-issue_date"]

    def __str__(self):
        return f"Attestation {self.reference} — {self.participant}"

    @property
    def is_valid(self):
        return self.valid_until >= timezone.now().date()

    @property
    def is_expired(self):
        return not self.is_valid

    @property
    def days_until_expiry(self):
        delta = (self.valid_until - timezone.now().date()).days
        return max(delta, 0)

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = self._generate_reference()
        if not self.valid_until:
            from core.models import FormationInfo

            years = FormationInfo.get_instance().attestation_validity_years or 5
            self.valid_until = self.issue_date + timedelta(days=365 * years)
        super().save(*args, **kwargs)

    @staticmethod
    def _generate_reference():
        """
        Generate a sequential unique reference using select_for_update
        inside a transaction to prevent race conditions under concurrent saves.
        """
        from django.utils import timezone as tz

        year = tz.now().year
        with transaction.atomic():
            count = (
                Attestation.objects.select_for_update()
                .filter(issue_date__year=year)
                .count()
            ) + 1
        return f"ATT-{year}-{count:04d}"
