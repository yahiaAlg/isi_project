# =============================================================================
# reporting/utils.py  —  Dashboard & report KPI aggregations
# =============================================================================

from datetime import date
from decimal import Decimal

from django.db.models import Avg, Count, Q, Sum
from django.utils import timezone


def dashboard_kpis():
    """
    Compute all KPIs needed by the dashboard in as few queries as possible.
    Returns a flat dict consumed directly by the dashboard template context.
    """
    from clients.models import Client
    from etudes.models import StudyProject
    from financial.models import Expense, Invoice, Payment
    from formations.models import Session

    today = date.today()

    # ── Revenue (current year) ────────────────────────────────────────── #
    year_start = date(today.year, 1, 1)
    year_end = date(today.year, 12, 31)

    inv_year = Invoice.objects.filter(
        invoice_date__range=[year_start, year_end],
        status__in=[
            Invoice.STATUS_UNPAID,
            Invoice.STATUS_PARTIALLY_PAID,
            Invoice.STATUS_PAID,
        ],
    ).aggregate(
        total_ht=Sum("amount_ht"),
        formation_ht=Sum("amount_ht", filter=Q(invoice_type=Invoice.TYPE_FORMATION)),
        etude_ht=Sum("amount_ht", filter=Q(invoice_type=Invoice.TYPE_ETUDE)),
    )

    # ── Collections ───────────────────────────────────────────────────── #
    collected_year = Payment.objects.filter(
        date__range=[year_start, year_end],
        status=Payment.STATUS_CONFIRMED,
    ).aggregate(total=Sum("amount"))["total"] or Decimal("0")

    # ── Outstanding ───────────────────────────────────────────────────── #
    outstanding = Invoice.objects.filter(
        status__in=[Invoice.STATUS_UNPAID, Invoice.STATUS_PARTIALLY_PAID]
    ).aggregate(
        count=Count("pk"),
        total=Sum("amount_remaining"),
        overdue_count=Count("pk", filter=Q(due_date__lt=today)),
        overdue_total=Sum("amount_remaining", filter=Q(due_date__lt=today)),
    )

    # ── Sessions ──────────────────────────────────────────────────────── #
    sessions = Session.objects.aggregate(
        upcoming=Count(
            "pk", filter=Q(status=Session.STATUS_PLANNED, date_start__gte=today)
        ),
        in_progress=Count("pk", filter=Q(status=Session.STATUS_IN_PROGRESS)),
        completed_year=Count(
            "pk",
            filter=Q(
                status=Session.STATUS_COMPLETED,
                date_start__range=[year_start, year_end],
            ),
        ),
    )

    # ── Projects ──────────────────────────────────────────────────────── #
    projects = StudyProject.objects.aggregate(
        active=Count("pk", filter=Q(status=StudyProject.STATUS_IN_PROGRESS)),
        overdue=Count(
            "pk",
            filter=Q(
                status=StudyProject.STATUS_IN_PROGRESS,
                end_date__lt=today,
            ),
        ),
    )

    # ── Expenses (year) ───────────────────────────────────────────────── #
    expenses_year = Expense.objects.filter(
        date__range=[year_start, year_end],
        approval_status=Expense.APPROVAL_APPROVED,
    ).aggregate(total=Sum("amount"))["total"] or Decimal("0")

    # ── Expenses needing action ───────────────────────────────────────── #
    expenses_action = Expense.objects.filter(
        Q(receipt_missing=True) | Q(approval_status=Expense.APPROVAL_PENDING)
    ).count()

    total_ht = inv_year["total_ht"] or Decimal("0")

    return {
        # Revenue
        "ca_ht": total_ht,
        "ca_formation_ht": inv_year["formation_ht"] or Decimal("0"),
        "ca_etude_ht": inv_year["etude_ht"] or Decimal("0"),
        "collected_year": collected_year,
        "expenses_year": expenses_year,
        "gross_margin": total_ht - expenses_year,
        # Outstanding
        "outstanding_count": outstanding["count"] or 0,
        "outstanding_total": outstanding["total"] or Decimal("0"),
        "overdue_count": outstanding["overdue_count"] or 0,
        "overdue_total": outstanding["overdue_total"] or Decimal("0"),
        # Operations
        "sessions_upcoming": sessions["upcoming"] or 0,
        "sessions_in_progress": sessions["in_progress"] or 0,
        "sessions_completed_year": sessions["completed_year"] or 0,
        "projects_active": projects["active"] or 0,
        "projects_overdue": projects["overdue"] or 0,
        "expenses_need_action": expenses_action,
    }


def session_fill_rate_report(date_from=None, date_to=None):
    """
    Return sessions annotated with fill_rate for the fill-rate report.
    """
    from formations.models import Session
    from django.db.models import F, FloatField, ExpressionWrapper

    qs = Session.objects.filter(
        status__in=[Session.STATUS_COMPLETED, Session.STATUS_IN_PROGRESS]
    ).select_related("formation", "trainer", "client")

    if date_from:
        qs = qs.filter(date_start__gte=date_from)
    if date_to:
        qs = qs.filter(date_end__lte=date_to)

    return qs.annotate(
        participants_ann=Count("participants"),
        fill_pct=ExpressionWrapper(
            Count("participants") * 100.0 / F("capacity"),
            output_field=FloatField(),
        ),
    ).order_by("-date_start")


def trainer_utilization_report(date_from=None, date_to=None):
    """
    Return trainers annotated with session_count and total_days for the period.
    """
    from resources.models import Trainer
    from formations.models import Session
    from django.db.models import F

    qs = (
        Trainer.objects.filter(is_active=True)
        .annotate(
            period_sessions=Count(
                "sessions",
                filter=Q(
                    sessions__status__in=[
                        Session.STATUS_COMPLETED,
                        Session.STATUS_IN_PROGRESS,
                    ],
                    **({"sessions__date_start__gte": date_from} if date_from else {}),
                    **({"sessions__date_end__lte": date_to} if date_to else {}),
                ),
            )
        )
        .order_by("-period_sessions")
    )

    return qs


def equipment_utilization_report():
    """
    Return equipment list annotated with usage stats for the utilization report.
    """
    from resources.models import Equipment
    from django.conf import settings

    idle_threshold = getattr(settings, "EQUIPMENT_IDLE_THRESHOLD_DAYS", 90)
    today = date.today()

    qs = Equipment.objects.annotate(
        usage_count_ann=Count("usages"),
        total_hours_ann=Sum("usages__duration_hours"),
    ).order_by("status", "-usage_count_ann")

    return qs
