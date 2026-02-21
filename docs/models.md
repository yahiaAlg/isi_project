# ISI Backend - All Models

This file contains the exact content of all models.py files from each app.

---

## accounts/models.py

```python
"""
Accounts models — User Profile extension.
"""

from django.db import models
from django.contrib.auth.models import User

from core.base_models import TimeStampedModel


class UserProfile(TimeStampedModel):
    """
    Extended user profile with role-based access control.
    """

    ROLE_ADMIN = "admin"
    ROLE_RECEPTIONIST = "receptionist"

    ROLE_CHOICES = [
        (ROLE_ADMIN, "Administrateur"),
        (ROLE_RECEPTIONIST, "Réceptionniste"),
    ]

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="profile",
        verbose_name="Utilisateur",
    )
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default=ROLE_RECEPTIONIST,
        verbose_name="Rôle",
    )
    phone = models.CharField(max_length=50, blank=True, verbose_name="Téléphone")
    # Soft-disable an account without deleting it
    is_active = models.BooleanField(default=True, verbose_name="Actif")
    # Optional avatar
    avatar = models.ImageField(upload_to="avatars/", blank=True, verbose_name="Avatar")
    # Preferred display language (future i18n)
    language = models.CharField(max_length=10, default="fr", verbose_name="Langue")

    class Meta:
        verbose_name = "Profil utilisateur"
        verbose_name_plural = "Profils utilisateurs"

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} — {self.get_role_display()}"

    # ------------------------------------------------------------------ #
    # Role helpers
    # ------------------------------------------------------------------ #

    @property
    def is_admin(self):
        """True if user holds the administrator role."""
        return self.role == self.ROLE_ADMIN

    @property
    def is_receptionist(self):
        """True if user holds the receptionist role."""
        return self.role == self.ROLE_RECEPTIONIST

    @property
    def full_name(self):
        """Return the Django auth full name, falling back to username."""
        return self.user.get_full_name() or self.user.username

    @property
    def last_login(self):
        """Proxy to the underlying auth user last-login datetime."""
        return self.user.last_login
```

---

## clients/models.py

```python
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

**Fields:**
- `name` (CharField) - Centre name
- `description` (TextField) - Description
- `address` (TextField) - Specific address
- `phone` (CharField) - Specific phone
- `email` (EmailField) - Specific email
- `invoice_prefix` (CharField) - Invoice prefix (default: F)
- `tva_applicable` (BooleanField) - TVA applicable flag
- `tva_rate` (DecimalField) - TVA rate (default: 0.19)
- `director_name` (CharField) - Training director name
- `director_title` (CharField) - Director title
- `director_signature` (ImageField) - Director signature
- `attestation_validity_years` (PositiveIntegerField) - Attestation validity (default: 5)
- `min_attendance_percent` (PositiveIntegerField) - Minimum attendance required (default: 80)

---

## Etudes

### StudyProject
An industrial safety consulting project for a client.

**Fields:**
- `client` (ForeignKey → Client) - Client
- `title` (CharField) - Project title
- `reference` (CharField) - Internal reference (e.g., ETU-2026-001)
- `description` (TextField) - Project description
- `project_type` (CharField) - Mission type (e.g., Audit SST, Diagnostic incendie)
- `site_address` (TextField) - Intervention site address
- `start_date` (DateField) - Start date
- `end_date` (DateField) - Expected end date
- `actual_end_date` (DateField) - Actual end date
- `budget` (DecimalField) - Contractual budget (DA)
- `status` (CharField) - Status: in_progress, completed, on_hold, cancelled
- `priority` (CharField) - Priority: low, medium, high, urgent
- `notes` (TextField) - Notes

**Properties:**
- `phase_count` - Number of phases
- `completed_phase_count` - Number of completed phases
- `progress_percentage` - Completion percentage
- `total_expenses` - Sum of expenses allocated to this project
- `margin` - Budget minus expenses
- `margin_rate` - Margin as percentage of budget
- `is_overdue` - True if end_date passed and project still active
- `days_overdue` - Number of days overdue
- `can_be_closed` - True if all phases completed

### ProjectPhase
A discrete phase within a study project.

**Fields:**
- `project` (ForeignKey → StudyProject) - Parent project
- `name` (CharField) - Phase name
- `description` (TextField) - Description
- `order` (PositiveIntegerField) - Display order
- `status` (CharField) - Status: pending, in_progress, completed, blocked
- `start_date` (DateField) - Start date
- `due_date` (DateField) - Due date
- `completion_date` (DateField) - Actual completion date
- `estimated_hours` (DecimalField) - Estimated hours
- `actual_hours` (DecimalField) - Actual hours spent
- `deliverable` (CharField) - Expected deliverable summary
- `notes` (TextField) - Notes

**Properties:**
- `is_overdue` - True if due_date passed and not completed
- `deliverable_count` - Number of deliverables

### ProjectDeliverable
A document or output produced during a project phase.

**Fields:**
- `phase` (ForeignKey → ProjectPhase) - Parent phase
- `title` (CharField) - Deliverable title
- `description` (TextField) - Description
- `document` (FileField) - File upload
- `version` (CharField) - Version number
- `submitted_to` (CharField) - Recipient name
- `submission_date` (DateField) - Submission date
- `client_approved` (BooleanField/null) - Client approval status
- `notes` (TextField) - Notes

---

## Financial

### Invoice
An invoice issued to a client after service delivery.

**Fields:**
- `invoice_type` (CharField) - Type: formation or etude
- `reference` (CharField) - Invoice number (auto-generated: F-YYYY-NNN or E-YYYY-NNN)
- `client` (ForeignKey → Client) - Client
- `invoice_date` (DateField) - Invoice date
```
