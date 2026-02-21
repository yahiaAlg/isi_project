# =============================================================================
# financial/utils.py  —  Reference generation, date helpers, report builders
# =============================================================================

from datetime import date
from decimal import Decimal

from django.db.models import Count, Q, Sum


# ── Reference generation ────────────────────────────────────────────────── #


def next_invoice_reference(invoice_type, invoice_date=None):
    """
    Generate the next sequential invoice reference for a given type + year.
    Delegates to Invoice._next_reference so logic lives in one place.
    """
    from financial.models import Invoice

    year = (invoice_date or date.today()).year
    return Invoice._next_reference(invoice_type, year)


def next_credit_note_reference(cn_date=None):
    from financial.models import CreditNote

    year = (cn_date or date.today()).year
    return CreditNote._next_reference(year)


# ── Date range helpers ───────────────────────────────────────────────────── #


def resolve_date_range(form_cleaned_data):
    """
    Given cleaned data from ReportFilterForm, return (date_from, date_to).
    Prefers an explicit FinancialPeriod over manual date fields.
    """
    period = form_cleaned_data.get("period")
    if period:
        return period.date_start, period.date_end
    return form_cleaned_data["date_from"], form_cleaned_data["date_to"]


def current_year_range():
    """Return (Jan 1, Dec 31) for the current calendar year."""
    y = date.today().year
    return date(y, 1, 1), date(y, 12, 31)


# ── Revenue aggregates ───────────────────────────────────────────────────── #


def revenue_summary(date_from, date_to, invoice_type=None):
    """
    Return a dict with invoiced HT, collected, outstanding, and expense totals
    for the given date range, optionally filtered by invoice type.
    """
    from financial.models import Expense, Invoice, Payment

    inv_qs = Invoice.objects.filter(
        invoice_date__range=[date_from, date_to],
        status__in=[
            Invoice.STATUS_UNPAID,
            Invoice.STATUS_PARTIALLY_PAID,
            Invoice.STATUS_PAID,
        ],
    )
    if invoice_type:
        inv_qs = inv_qs.filter(invoice_type=invoice_type)

    pay_qs = Payment.objects.filter(
        date__range=[date_from, date_to],
        status=Payment.STATUS_CONFIRMED,
    )
    if invoice_type:
        pay_qs = pay_qs.filter(invoice__invoice_type=invoice_type)

    exp_qs = Expense.objects.filter(
        date__range=[date_from, date_to],
        approval_status=Expense.APPROVAL_APPROVED,
    )

    totals = inv_qs.aggregate(
        invoiced_ht=Sum("amount_ht"),
        invoiced_ttc=Sum("amount_ttc"),
        outstanding=Sum("amount_remaining"),
    )
    collected = pay_qs.aggregate(total=Sum("amount"))["total"] or Decimal("0")
    expenses = exp_qs.aggregate(total=Sum("amount"))["total"] or Decimal("0")

    invoiced_ht = totals["invoiced_ht"] or Decimal("0")
    return {
        "invoiced_ht": invoiced_ht,
        "invoiced_ttc": totals["invoiced_ttc"] or Decimal("0"),
        "outstanding": totals["outstanding"] or Decimal("0"),
        "collected": collected,
        "expenses": expenses,
        "gross_margin": invoiced_ht - expenses,
        "margin_rate": (
            round(((invoiced_ht - expenses) / invoiced_ht) * 100, 1)
            if invoiced_ht
            else Decimal("0")
        ),
    }


def revenue_by_month(date_from, date_to):
    """
    Return a list of dicts [{month, formation_ht, etude_ht, total_ht}, ...]
    ordered by month, suitable for chart rendering.
    """
    from financial.models import Invoice
    from django.db.models.functions import TruncMonth

    rows = (
        Invoice.objects.filter(
            invoice_date__range=[date_from, date_to],
            status__in=[
                Invoice.STATUS_UNPAID,
                Invoice.STATUS_PARTIALLY_PAID,
                Invoice.STATUS_PAID,
            ],
        )
        .annotate(month=TruncMonth("invoice_date"))
        .values("month", "invoice_type")
        .annotate(total_ht=Sum("amount_ht"))
        .order_by("month")
    )

    # Pivot into month → {formation, etude}
    pivot = {}
    for row in rows:
        m = row["month"].strftime("%Y-%m")
        pivot.setdefault(
            m, {"month": m, "formation_ht": Decimal("0"), "etude_ht": Decimal("0")}
        )
        if row["invoice_type"] == Invoice.TYPE_FORMATION:
            pivot[m]["formation_ht"] = row["total_ht"]
        else:
            pivot[m]["etude_ht"] = row["total_ht"]

    result = sorted(pivot.values(), key=lambda x: x["month"])
    for r in result:
        r["total_ht"] = r["formation_ht"] + r["etude_ht"]
    return result


def outstanding_invoices():
    """Return unpaid/partially-paid invoices ordered by oldest first."""
    from financial.models import Invoice

    return (
        Invoice.objects.filter(
            status__in=[Invoice.STATUS_UNPAID, Invoice.STATUS_PARTIALLY_PAID]
        )
        .select_related("client")
        .order_by("invoice_date")
    )


def top_clients_by_revenue(limit=10, date_from=None, date_to=None):
    """Return queryset of clients annotated with total_paid, ordered desc."""
    from financial.models import Invoice
    from clients.models import Client

    inv_qs = Invoice.objects.filter(status=Invoice.STATUS_PAID)
    if date_from:
        inv_qs = inv_qs.filter(invoice_date__gte=date_from)
    if date_to:
        inv_qs = inv_qs.filter(invoice_date__lte=date_to)

    return (
        Client.objects.filter(invoices__in=inv_qs)
        .annotate(total_paid=Sum("invoices__amount_ttc"))
        .order_by("-total_paid")[:limit]
    )


# ── Session margin ───────────────────────────────────────────────────────── #


def session_margin(session):
    """
    Return {revenue, expenses, margin, margin_rate} for a single session.
    Revenue = effective_price × attended participants.
    """
    from financial.models import Expense

    revenue = session.total_revenue
    expenses = Expense.objects.filter(allocated_to_session=session).aggregate(
        total=Sum("amount")
    )["total"] or Decimal("0")
    margin = revenue - expenses
    return {
        "revenue": revenue,
        "expenses": expenses,
        "margin": margin,
        "margin_rate": round((margin / revenue * 100), 1) if revenue else Decimal("0"),
    }
