# etudes/resources.py

from import_export import fields, resources
from import_export.widgets import ForeignKeyWidget

from clients.models import Client
from etudes.models import ProjectDeliverable, ProjectPhase, StudyProject


class StudyProjectResource(resources.ModelResource):
    """
    Import/export study projects.
    ``client`` is matched by name on import.
    Financial and progress read-only columns are appended on export.
    """

    client = fields.Field(
        column_name="client",
        attribute="client",
        widget=ForeignKeyWidget(Client, field="name"),
    )

    # Read-only computed columns for export reports
    phase_count = fields.Field(column_name="nb_phases", readonly=True)
    progress = fields.Field(column_name="avancement_pct", readonly=True)
    total_expenses = fields.Field(column_name="depenses_da", readonly=True)
    margin = fields.Field(column_name="marge_da", readonly=True)
    margin_rate = fields.Field(column_name="taux_marge_pct", readonly=True)
    is_overdue = fields.Field(column_name="en_retard", readonly=True)

    class Meta:
        model = StudyProject
        import_id_fields = ["reference"]  # internal reference is the natural key
        fields = [
            "id",
            "client",
            "title",
            "reference",
            "project_type",
            "site_address",
            "start_date",
            "end_date",
            "actual_end_date",
            "budget",
            "status",
            "priority",
            "description",
            "notes",
            # computed exports
            "phase_count",
            "progress",
            "total_expenses",
            "margin",
            "margin_rate",
            "is_overdue",
        ]
        export_order = fields
        skip_unchanged = True
        report_skipped = True

    def before_import_row(self, row, **kwargs):
        # Normalise status code
        status_map = {
            "en cours": StudyProject.STATUS_IN_PROGRESS,
            "in_progress": StudyProject.STATUS_IN_PROGRESS,
            "terminé": StudyProject.STATUS_COMPLETED,
            "termine": StudyProject.STATUS_COMPLETED,
            "completed": StudyProject.STATUS_COMPLETED,
            "en pause": StudyProject.STATUS_ON_HOLD,
            "on_hold": StudyProject.STATUS_ON_HOLD,
            "annulé": StudyProject.STATUS_CANCELLED,
            "annule": StudyProject.STATUS_CANCELLED,
            "cancelled": StudyProject.STATUS_CANCELLED,
        }
        raw_status = str(row.get("status", "")).strip().lower()
        if raw_status in status_map:
            row["status"] = status_map[raw_status]
        else:
            row.setdefault("status", StudyProject.STATUS_IN_PROGRESS)

        priority_map = {
            "basse": StudyProject.PRIORITY_LOW,
            "low": StudyProject.PRIORITY_LOW,
            "normale": StudyProject.PRIORITY_MEDIUM,
            "medium": StudyProject.PRIORITY_MEDIUM,
            "haute": StudyProject.PRIORITY_HIGH,
            "high": StudyProject.PRIORITY_HIGH,
            "urgente": StudyProject.PRIORITY_URGENT,
            "urgent": StudyProject.PRIORITY_URGENT,
        }
        raw_priority = str(row.get("priority", "")).strip().lower()
        if raw_priority in priority_map:
            row["priority"] = priority_map[raw_priority]
        else:
            row.setdefault("priority", StudyProject.PRIORITY_MEDIUM)

    def dehydrate_phase_count(self, obj):
        return obj.phase_count

    def dehydrate_progress(self, obj):
        return f"{obj.progress_percentage}%"

    def dehydrate_total_expenses(self, obj):
        return obj.total_expenses

    def dehydrate_margin(self, obj):
        return obj.margin

    def dehydrate_margin_rate(self, obj):
        return f"{obj.margin_rate}%"

    def dehydrate_is_overdue(self, obj):
        return "Oui" if obj.is_overdue else "Non"

    def dehydrate_status(self, obj):
        return obj.get_status_display()

    def dehydrate_priority(self, obj):
        return obj.get_priority_display()


class ProjectPhaseResource(resources.ModelResource):
    """
    Export project phases — useful for project status reports.
    Import supported: allows bulk phase creation when migrating existing project data.
    ``project`` matched by its internal reference.
    """

    project = fields.Field(
        column_name="project_reference",
        attribute="project",
        widget=ForeignKeyWidget(StudyProject, field="reference"),
    )
    is_overdue = fields.Field(column_name="en_retard", readonly=True)

    class Meta:
        model = ProjectPhase
        import_id_fields = ["project", "name"]
        fields = [
            "id",
            "project",
            "name",
            "order",
            "status",
            "start_date",
            "due_date",
            "completion_date",
            "estimated_hours",
            "actual_hours",
            "deliverable",
            "description",
            "notes",
            "is_overdue",
        ]
        export_order = fields
        skip_unchanged = True

    def before_import_row(self, row, **kwargs):
        status_map = {
            "en attente": ProjectPhase.STATUS_PENDING,
            "pending": ProjectPhase.STATUS_PENDING,
            "en cours": ProjectPhase.STATUS_IN_PROGRESS,
            "in_progress": ProjectPhase.STATUS_IN_PROGRESS,
            "terminée": ProjectPhase.STATUS_COMPLETED,
            "terminee": ProjectPhase.STATUS_COMPLETED,
            "completed": ProjectPhase.STATUS_COMPLETED,
            "bloquée": ProjectPhase.STATUS_BLOCKED,
            "bloquee": ProjectPhase.STATUS_BLOCKED,
            "blocked": ProjectPhase.STATUS_BLOCKED,
        }
        raw = str(row.get("status", "")).strip().lower()
        if raw in status_map:
            row["status"] = status_map[raw]
        else:
            row.setdefault("status", ProjectPhase.STATUS_PENDING)

    def dehydrate_is_overdue(self, obj):
        return "Oui" if obj.is_overdue else "Non"

    def dehydrate_status(self, obj):
        return obj.get_status_display()
