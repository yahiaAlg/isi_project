# formations/resources.py

from import_export import fields, resources
from import_export.widgets import ForeignKeyWidget

from clients.models import Client
from formations.models import (
    Attestation,
    Formation,
    FormationCategory,
    Participant,
    Session,
)
from resources.models import Trainer, TrainingRoom


class FormationCategoryResource(resources.ModelResource):
    class Meta:
        model = FormationCategory
        import_id_fields = ["name"]
        fields = ["id", "name", "description", "color"]
        skip_unchanged = True


class FormationResource(resources.ModelResource):
    """
    Export/import the training catalogue.
    ``category`` is matched by category name on import.
    ``slug`` is auto-generated on save if blank.
    """

    category = fields.Field(
        column_name="category",
        attribute="category",
        widget=ForeignKeyWidget(FormationCategory, field="name"),
    )

    class Meta:
        model = Formation
        import_id_fields = ["slug"]
        fields = [
            "id",
            "category",
            "title",
            "slug",
            "description",
            "objectives",
            "target_audience",
            "prerequisites",
            "duration_days",
            "duration_hours",
            "base_price",
            "max_participants",
            "min_participants",
            "accreditation_body",
            "accreditation_reference",
            "is_active",
        ]
        export_order = fields
        skip_unchanged = True
        report_skipped = True

    def before_import_row(self, row, **kwargs):
        # Auto-generate slug from title if missing
        if not row.get("slug") and row.get("title"):
            from django.utils.text import slugify

            row["slug"] = slugify(row["title"])

        # Normalise boolean
        active_raw = str(row.get("is_active", "1")).strip().lower()
        row["is_active"] = active_raw not in ("0", "false", "faux", "non", "no", "")

    def dehydrate_is_active(self, obj):
        return "Oui" if obj.is_active else "Non"


class SessionResource(resources.ModelResource):
    """
    Export sessions.  Import is intentionally read-only for most fields —
    sessions should be created through the UI to enforce all business rules.
    This resource is primarily used for data migration and reporting exports.
    """

    formation = fields.Field(
        column_name="formation",
        attribute="formation",
        widget=ForeignKeyWidget(Formation, field="title"),
    )
    client = fields.Field(
        column_name="client",
        attribute="client",
        widget=ForeignKeyWidget(Client, field="name"),
    )
    trainer = fields.Field(
        column_name="trainer",
        attribute="trainer",
        widget=ForeignKeyWidget(Trainer, field="email"),
    )
    room = fields.Field(
        column_name="room",
        attribute="room",
        widget=ForeignKeyWidget(TrainingRoom, field="name"),
    )
    # Computed read-only export columns
    participant_count = fields.Field(column_name="participant_count", readonly=True)
    fill_rate = fields.Field(column_name="fill_rate_pct", readonly=True)
    total_revenue = fields.Field(column_name="total_revenue_da", readonly=True)

    class Meta:
        model = Session
        import_id_fields = ["id"]
        fields = [
            "id",
            "formation",
            "client",
            "date_start",
            "date_end",
            "trainer",
            "room",
            "external_location",
            "capacity",
            "price_per_participant",
            "status",
            # read-only exports below
            "participant_count",
            "fill_rate",
            "total_revenue",
        ]
        export_order = fields
        skip_unchanged = True

    def dehydrate_participant_count(self, obj):
        return obj.participant_count

    def dehydrate_fill_rate(self, obj):
        return f"{obj.fill_rate}%"

    def dehydrate_total_revenue(self, obj):
        return obj.total_revenue

    def dehydrate_status(self, obj):
        return obj.get_status_display()


class ParticipantResource(resources.ModelResource):
    """
    Primary resource for bulk participant import/export.
    ``session`` is matched by its PK on import (safest for bulk ops).

    Import columns:
        session_id, first_name, last_name, employer, email,
        phone, job_title, attended
    """

    session = fields.Field(
        column_name="session_id",
        attribute="session",
        widget=ForeignKeyWidget(Session, field="pk"),
    )
    employer_client = fields.Field(
        column_name="employer_client",
        attribute="employer_client",
        widget=ForeignKeyWidget(Client, field="name"),
    )

    class Meta:
        model = Participant
        import_id_fields = ["session", "first_name", "last_name", "email"]
        fields = [
            "id",
            "session",
            "first_name",
            "last_name",
            "employer",
            "employer_client",
            "phone",
            "email",
            "job_title",
            "attended",
        ]
        export_order = fields
        skip_unchanged = True
        report_skipped = True

    def before_import_row(self, row, **kwargs):
        attended_raw = str(row.get("attended", "1")).strip().lower()
        row["attended"] = attended_raw not in (
            "0",
            "false",
            "faux",
            "non",
            "no",
            "absent",
            "",
        )

    def skip_row(self, instance, original, row, import_validation_errors=None):
        """Skip if session is full and participant is new."""
        if not instance.pk:
            session = instance.session
            if session and session.is_full:
                return True
        return super().skip_row(instance, original, row, import_validation_errors)

    def dehydrate_attended(self, obj):
        return "Oui" if obj.attended else "Non"


class AttestationResource(resources.ModelResource):
    """
    Export-only resource — attestations are always generated by the system,
    never imported.  Useful for audits and certificate registers.
    """

    participant_name = fields.Field(column_name="participant", readonly=True)
    formation_title = fields.Field(column_name="formation", readonly=True)
    session_date = fields.Field(column_name="session_date", readonly=True)
    is_valid = fields.Field(column_name="valide", readonly=True)

    class Meta:
        model = Attestation
        fields = [
            "id",
            "reference",
            "participant_name",
            "formation_title",
            "session_date",
            "issue_date",
            "valid_until",
            "is_valid",
        ]
        export_order = fields

    def dehydrate_participant_name(self, obj):
        return obj.participant.full_name

    def dehydrate_formation_title(self, obj):
        return obj.session.formation.title

    def dehydrate_session_date(self, obj):
        return obj.session.date_start

    def dehydrate_is_valid(self, obj):
        return "Oui" if obj.is_valid else "Non (expirée)"
