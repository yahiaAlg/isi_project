# financial/views.py

from decimal import Decimal

from django.contrib import messages
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from core.utils import admin_required
from financial.forms import (
    CreditNoteForm,
    ExpenseCategoryForm,
    ExpenseFilterForm,
    ExpenseForm,
    FinancialPeriodForm,
    InvoiceFilterForm,
    InvoiceForm,
    InvoiceItemForm,
    PaymentForm,
    ReportFilterForm,
)
from financial.models import (
    CreditNote,
    Expense,
    ExpenseCategory,
    FinancialPeriod,
    Invoice,
    InvoiceItem,
    Payment,
)
from financial.utils import (
    current_year_range,
    outstanding_invoices,
    resolve_date_range,
    revenue_by_month,
    revenue_summary,
    session_margin,
    top_clients_by_revenue,
)


# ---------------------------------------------------------------------------
# Invoices
# ---------------------------------------------------------------------------


@admin_required
def invoice_list(request):
    qs = Invoice.objects.select_related("client").all()
    form = InvoiceFilterForm(request.GET or None)

    if form.is_valid():
        q = form.cleaned_data.get("q")
        status = form.cleaned_data.get("status")
        invoice_type = form.cleaned_data.get("invoice_type")
        date_from = form.cleaned_data.get("date_from")
        date_to = form.cleaned_data.get("date_to")
        client = form.cleaned_data.get("client")

        if q:
            from django.db.models import Q

            qs = qs.filter(Q(reference__icontains=q) | Q(client__name__icontains=q))
        if status:
            qs = qs.filter(status=status)
        if invoice_type:
            qs = qs.filter(invoice_type=invoice_type)
        if date_from:
            qs = qs.filter(invoice_date__gte=date_from)
        if date_to:
            qs = qs.filter(invoice_date__lte=date_to)
        if client:
            qs = qs.filter(client=client)

    paginator = Paginator(qs.order_by("-invoice_date"), 25)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "financial/invoice_list.html",
        {"page_obj": page_obj, "filter_form": form, "today": timezone.now().date()},
    )


@admin_required
def invoice_detail(request, pk):
    invoice = get_object_or_404(
        Invoice.objects.select_related("client").prefetch_related("items", "payments"),
        pk=pk,
    )
    return render(request, "financial/invoice_detail.html", {"invoice": invoice})


@admin_required
def invoice_create(request):
    form = InvoiceForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        invoice = form.save()
        messages.success(request, f"Facture {invoice.reference} créée.")
        return redirect("financial:invoice_detail", pk=invoice.pk)
    return render(
        request,
        "financial/invoice_form.html",
        {"form": form, "action": "Nouvelle facture"},
    )


@admin_required
def invoice_create_from_session(request, session_pk):
    """Pre-populate an invoice from a completed training session."""
    from formations.models import Session

    session = get_object_or_404(Session, pk=session_pk)

    if not session.can_be_invoiced:
        messages.error(
            request, "La session doit être terminée avant de pouvoir être facturée."
        )
        return redirect("formations:session_detail", pk=session_pk)

    initial = {
        "client": session.client,
        "invoice_type": Invoice.TYPE_FORMATION,
        "invoice_date": timezone.now().date(),
    }
    form = InvoiceForm(request.POST or None, initial=initial)

    if request.method == "POST" and form.is_valid():
        invoice = form.save(commit=False)
        invoice.save()
        # Auto-create a line item from session data
        InvoiceItem.objects.create(
            invoice=invoice,
            description=f"{session.formation.title} — {session.date_start} au {session.date_end}",
            quantity=session.attended_count,
            unit_price=session.effective_price,
        )
        messages.success(
            request, f"Facture {invoice.reference} créée depuis la session."
        )
        return redirect("financial:invoice_detail", pk=invoice.pk)

    return render(
        request,
        "financial/invoice_form.html",
        {"form": form, "action": "Facturer la session", "source_session": session},
    )


@admin_required
def invoice_create_from_project(request, project_pk):
    """Pre-populate an invoice from a study project."""
    from etudes.models import StudyProject

    project = get_object_or_404(StudyProject, pk=project_pk)

    initial = {
        "client": project.client,
        "invoice_type": Invoice.TYPE_ETUDE,
        "invoice_date": timezone.now().date(),
    }
    form = InvoiceForm(request.POST or None, initial=initial)

    if request.method == "POST" and form.is_valid():
        invoice = form.save(commit=False)
        invoice.save()
        InvoiceItem.objects.create(
            invoice=invoice,
            description=f"{project.title}",
            quantity=1,
            unit_price=project.budget,
        )
        messages.success(
            request, f"Facture {invoice.reference} créée depuis le projet."
        )
        return redirect("financial:invoice_detail", pk=invoice.pk)

    return render(
        request,
        "financial/invoice_form.html",
        {"form": form, "action": "Facturer le projet", "source_project": project},
    )


@admin_required
def invoice_edit(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    if invoice.status == Invoice.STATUS_VOIDED:
        messages.error(request, "Une facture annulée ne peut pas être modifiée.")
        return redirect("financial:invoice_detail", pk=pk)

    form = InvoiceForm(request.POST or None, instance=invoice)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Facture mise à jour.")
        return redirect("financial:invoice_detail", pk=pk)

    return render(
        request,
        "financial/invoice_form.html",
        {"form": form, "action": "Modifier", "invoice": invoice},
    )


@admin_required
def invoice_void(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    if invoice.status == Invoice.STATUS_VOIDED:
        messages.error(request, "Cette facture est déjà annulée.")
        return redirect("financial:invoice_detail", pk=pk)

    form = VoidInvoiceForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        invoice.status = Invoice.STATUS_VOIDED
        reason = form.cleaned_data.get("reason", "")
        if reason:
            invoice.notes = (invoice.notes + "\nAnnulation: " + reason).strip()
        invoice.save(update_fields=["status", "notes"])
        messages.success(request, f"Facture {invoice.reference} annulée.")
        return redirect("financial:invoice_detail", pk=pk)

    return render(
        request,
        "financial/invoice_void.html",
        {"form": form, "invoice": invoice},
    )


@admin_required
def invoice_print(request, pk):
    from core.models import BureauEtudeInfo, FormationInfo, InstituteInfo

    invoice = get_object_or_404(
        Invoice.objects.select_related("client").prefetch_related("items"),
        pk=pk,
    )
    institute = InstituteInfo.get_instance()
    business_info = (
        FormationInfo.get_instance()
        if invoice.invoice_type == Invoice.TYPE_FORMATION
        else BureauEtudeInfo.get_instance()
    )
    return render(
        request,
        "financial/invoice_print.html",
        {"invoice": invoice, "institute": institute, "business_info": business_info},
    )


# ---------------------------------------------------------------------------
# Invoice line items
# ---------------------------------------------------------------------------


@admin_required
def item_add(request, invoice_pk):
    invoice = get_object_or_404(Invoice, pk=invoice_pk)
    form = InvoiceItemForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        item = form.save(commit=False)
        item.invoice = invoice
        item.save()
        # Signal fires recalculate_amounts()
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse(
                {
                    "status": "ok",
                    "amount_ht": str(invoice.amount_ht),
                    "amount_ttc": str(invoice.amount_ttc),
                }
            )
        messages.success(request, "Ligne ajoutée.")
        return redirect("financial:invoice_detail", pk=invoice_pk)

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"status": "error", "errors": form.errors}, status=400)
    return render(
        request,
        "financial/item_form.html",
        {"form": form, "invoice": invoice, "action": "Ajouter une ligne"},
    )


@admin_required
def item_edit(request, invoice_pk, pk):
    invoice = get_object_or_404(Invoice, pk=invoice_pk)
    item = get_object_or_404(InvoiceItem, pk=pk, invoice=invoice)
    form = InvoiceItemForm(request.POST or None, instance=item)

    if request.method == "POST" and form.is_valid():
        form.save()
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"status": "ok"})
        messages.success(request, "Ligne mise à jour.")
        return redirect("financial:invoice_detail", pk=invoice_pk)

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"status": "error", "errors": form.errors}, status=400)
    return render(
        request,
        "financial/item_form.html",
        {"form": form, "invoice": invoice, "action": "Modifier"},
    )


@admin_required
def item_delete(request, invoice_pk, pk):
    if request.method != "POST":
        return redirect("financial:invoice_detail", pk=invoice_pk)
    item = get_object_or_404(InvoiceItem, pk=pk, invoice_id=invoice_pk)
    item.delete()
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"status": "ok"})
    messages.success(request, "Ligne supprimée.")
    return redirect("financial:invoice_detail", pk=invoice_pk)


# ---------------------------------------------------------------------------
# Payments
# ---------------------------------------------------------------------------


@admin_required
def payment_add(request, invoice_pk, pk=None):
    invoice = get_object_or_404(Invoice, pk=invoice_pk)
    is_edit = pk is not None

    if not is_edit and invoice.status in [Invoice.STATUS_PAID, Invoice.STATUS_VOIDED]:
        messages.error(request, "Cette facture ne peut plus recevoir de paiement.")
        return redirect("financial:invoice_detail", pk=invoice_pk)

    if is_edit:
        payment = get_object_or_404(Payment, pk=pk, invoice=invoice)
    else:
        payment_count = invoice.payments.count() + 1
        auto_reference = (
            f"PAY-{timezone.now().year}-{invoice.reference}-{payment_count:04d}"
        )
        payment = Payment(
            invoice=invoice,
            date=timezone.now().date(),
            amount=invoice.amount_remaining,
            reference=auto_reference,
        )

    if request.method == "POST":
        form = PaymentForm(request.POST, instance=payment)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                "Paiement mis à jour." if is_edit else "Paiement enregistré.",
            )
            return redirect("financial:invoice_detail", pk=invoice_pk)
    else:
        form = PaymentForm(instance=payment)

    return render(
        request,
        "financial/payment_form.html",
        {
            "form": form,
            "invoice": invoice,
            "action": "Modifier le paiement" if is_edit else "Enregistrer un paiement",
        },
    )


@admin_required
def payment_delete(request, invoice_pk, pk):
    if request.method != "POST":
        return redirect("financial:invoice_detail", pk=invoice_pk)
    payment = get_object_or_404(Payment, pk=pk, invoice_id=invoice_pk)
    payment.delete()
    messages.success(request, "Paiement supprimé.")
    return redirect("financial:invoice_detail", pk=invoice_pk)


@admin_required
def payment_confirm(request, invoice_pk, pk):
    if request.method != "POST":
        return redirect("financial:invoice_detail", pk=invoice_pk)
    payment = get_object_or_404(Payment, pk=pk, invoice_id=invoice_pk)
    payment.status = Payment.STATUS_CONFIRMED
    payment.save(update_fields=["status"])
    messages.success(request, "Paiement confirmé.")
    return redirect("financial:invoice_detail", pk=invoice_pk)


@admin_required
def payment_reverse(request, invoice_pk, pk):
    if request.method != "POST":
        return redirect("financial:invoice_detail", pk=invoice_pk)
    payment = get_object_or_404(Payment, pk=pk, invoice_id=invoice_pk)
    payment.status = Payment.STATUS_REVERSED
    payment.save(update_fields=["status"])
    messages.success(request, "Paiement annulé/reversé.")
    return redirect("financial:invoice_detail", pk=invoice_pk)


# ---------------------------------------------------------------------------
# Credit notes
# ---------------------------------------------------------------------------


@admin_required
def credit_note_list(request):
    notes = CreditNote.objects.select_related("invoice__client").order_by("-date")
    paginator = Paginator(notes, 25)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(request, "financial/credit_note_list.html", {"page_obj": page_obj})


@admin_required
def credit_note_create(request, invoice_pk):
    invoice = get_object_or_404(Invoice, pk=invoice_pk)
    form = CreditNoteForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        cn = form.save(commit=False)
        cn.invoice = invoice
        cn.save()
        messages.success(request, f"Avoir {cn.reference} créé.")
        return redirect("financial:credit_note_detail", pk=cn.pk)

    return render(
        request,
        "financial/credit_note_form.html",
        {"form": form, "invoice": invoice},
    )


@admin_required
def credit_note_detail(request, pk):
    cn = get_object_or_404(CreditNote.objects.select_related("invoice__client"), pk=pk)
    return render(request, "financial/credit_note_detail.html", {"credit_note": cn})


@admin_required
def credit_note_print(request, pk):
    from core.models import BureauEtudeInfo, FormationInfo, InstituteInfo

    cn = get_object_or_404(CreditNote.objects.select_related("invoice__client"), pk=pk)
    institute = InstituteInfo.get_instance()
    business_info = (
        FormationInfo.get_instance()
        if cn.invoice.invoice_type == Invoice.TYPE_FORMATION
        else BureauEtudeInfo.get_instance()
    )
    return render(
        request,
        "financial/credit_note_print.html",
        {"credit_note": cn, "institute": institute, "business_info": business_info},
    )


# ---------------------------------------------------------------------------
# Expenses
# ---------------------------------------------------------------------------


@admin_required
def expense_list(request):
    qs = Expense.objects.select_related(
        "category", "allocated_to_session__formation", "allocated_to_project__client"
    ).all()
    form = ExpenseFilterForm(request.GET or None)

    if form.is_valid():
        q = form.cleaned_data.get("q")
        category = form.cleaned_data.get("category")
        approval_status = form.cleaned_data.get("approval_status")
        date_from = form.cleaned_data.get("date_from")
        date_to = form.cleaned_data.get("date_to")
        allocation = form.cleaned_data.get("allocation")

        if q:
            from django.db.models import Q

            qs = qs.filter(Q(description__icontains=q) | Q(category__name__icontains=q))
        if category:
            qs = qs.filter(category=category)
        if approval_status:
            qs = qs.filter(approval_status=approval_status)
        if date_from:
            qs = qs.filter(date__gte=date_from)
        if date_to:
            qs = qs.filter(date__lte=date_to)
        if allocation == "session":
            qs = qs.filter(allocated_to_session__isnull=False)
        elif allocation == "project":
            qs = qs.filter(allocated_to_project__isnull=False)
        elif allocation == "overhead":
            qs = qs.filter(
                allocated_to_session__isnull=True, allocated_to_project__isnull=True
            )

    paginator = Paginator(qs.order_by("-date"), 25)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "financial/expense_list.html",
        {"page_obj": page_obj, "filter_form": form},
    )


@admin_required
def expense_create(request):
    form = ExpenseForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        expense = form.save()
        messages.success(request, "Dépense enregistrée.")
        return redirect("financial:expense_list")
    return render(
        request,
        "financial/expense_form.html",
        {"form": form, "action": "Nouvelle dépense"},
    )


@admin_required
def expense_edit(request, pk):
    expense = get_object_or_404(Expense, pk=pk)
    form = ExpenseForm(request.POST or None, request.FILES or None, instance=expense)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Dépense mise à jour.")
        return redirect("financial:expense_list")
    return render(
        request,
        "financial/expense_form.html",
        {"form": form, "action": "Modifier", "expense": expense},
    )


@admin_required
def expense_delete(request, pk):
    if request.method != "POST":
        return redirect("financial:expense_list")
    expense = get_object_or_404(Expense, pk=pk)
    expense.delete()
    messages.success(request, "Dépense supprimée.")
    return redirect("financial:expense_list")


@admin_required
def expense_approve(request, pk):
    if request.method != "POST":
        return redirect("financial:expense_list")
    expense = get_object_or_404(Expense, pk=pk)
    expense.approval_status = Expense.APPROVAL_APPROVED
    expense.save(update_fields=["approval_status"])
    messages.success(request, "Dépense approuvée.")
    return redirect("financial:expense_list")


@admin_required
def expense_reject(request, pk):
    if request.method != "POST":
        return redirect("financial:expense_list")
    expense = get_object_or_404(Expense, pk=pk)
    expense.approval_status = Expense.APPROVAL_REJECTED
    expense.save(update_fields=["approval_status"])
    messages.success(request, "Dépense rejetée.")
    return redirect("financial:expense_list")


# ---------------------------------------------------------------------------
# Expense categories
# ---------------------------------------------------------------------------


@admin_required
def expense_category_list(request):
    categories = ExpenseCategory.objects.annotate(
        expense_count=__import__("django.db.models", fromlist=["Count"]).Count(
            "expenses"
        )
    )
    return render(
        request,
        "financial/expense_category_list.html",
        {"categories": categories},
    )


@admin_required
def expense_category_create(request):
    form = ExpenseCategoryForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        cat = form.save()
        messages.success(request, f"Catégorie « {cat.name} » créée.")
        return redirect("financial:expense_category_list")
    return render(
        request,
        "financial/expense_category_form.html",
        {"form": form, "action": "Nouvelle catégorie"},
    )


@admin_required
def expense_category_edit(request, pk):
    category = get_object_or_404(ExpenseCategory, pk=pk)
    form = ExpenseCategoryForm(request.POST or None, instance=category)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Catégorie mise à jour.")
        return redirect("financial:expense_category_list")
    return render(
        request,
        "financial/expense_category_form.html",
        {"form": form, "action": "Modifier"},
    )


# ---------------------------------------------------------------------------
# Financial periods
# ---------------------------------------------------------------------------


@admin_required
def period_list(request):
    periods = FinancialPeriod.objects.order_by("-date_start")
    return render(request, "financial/period_list.html", {"periods": periods})


@admin_required
def period_create(request):
    form = FinancialPeriodForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        period = form.save()
        messages.success(request, f"Période « {period} » créée.")
        return redirect("financial:period_detail", pk=period.pk)
    return render(
        request,
        "financial/period_form.html",
        {"form": form, "action": "Nouvelle période"},
    )


@admin_required
def period_detail(request, pk):
    period = get_object_or_404(FinancialPeriod, pk=pk)
    summary = revenue_summary(period.date_start, period.date_end)
    return render(
        request,
        "financial/period_detail.html",
        {"period": period, "summary": summary},
    )


@admin_required
def period_edit(request, pk):
    period = get_object_or_404(FinancialPeriod, pk=pk)
    form = FinancialPeriodForm(request.POST or None, instance=period)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Période mise à jour.")
        return redirect("financial:period_detail", pk=pk)
    return render(
        request,
        "financial/period_form.html",
        {"form": form, "action": "Modifier", "period": period},
    )


@admin_required
def period_close(request, pk):
    if request.method != "POST":
        return redirect("financial:period_detail", pk=pk)
    period = get_object_or_404(FinancialPeriod, pk=pk)
    if period.is_closed:
        messages.error(request, "Cette période est déjà clôturée.")
        return redirect("financial:period_detail", pk=pk)
    period.is_closed = True
    period.save(update_fields=["is_closed"])
    messages.success(request, f"Période « {period} » clôturée.")
    return redirect("financial:period_detail", pk=pk)


# ---------------------------------------------------------------------------
# Analytics & reports
# ---------------------------------------------------------------------------


@admin_required
def financial_analytics(request):
    date_from, date_to = current_year_range()
    summary_all = revenue_summary(date_from, date_to)
    summary_formation = revenue_summary(
        date_from, date_to, invoice_type=Invoice.TYPE_FORMATION
    )
    summary_etude = revenue_summary(date_from, date_to, invoice_type=Invoice.TYPE_ETUDE)
    unpaid = outstanding_invoices()[:10]
    top_clients = top_clients_by_revenue(limit=5, date_from=date_from, date_to=date_to)

    return render(
        request,
        "financial/analytics.html",
        {
            "summary_all": summary_all,
            "summary_formation": summary_formation,
            "summary_etude": summary_etude,
            "unpaid_invoices": unpaid,
            "top_clients": top_clients,
            "date_from": date_from,
            "date_to": date_to,
        },
    )


@admin_required
def revenue_report(request):
    form = ReportFilterForm(request.GET or None)
    date_from, date_to = current_year_range()

    if form.is_valid():
        date_from, date_to = resolve_date_range(form.cleaned_data)

    summary = revenue_summary(date_from, date_to)
    summary_formation = revenue_summary(
        date_from, date_to, invoice_type=Invoice.TYPE_FORMATION
    )
    summary_etude = revenue_summary(date_from, date_to, invoice_type=Invoice.TYPE_ETUDE)
    monthly = revenue_by_month(date_from, date_to)
    top_clients = top_clients_by_revenue(limit=10, date_from=date_from, date_to=date_to)

    return render(
        request,
        "financial/revenue_report.html",
        {
            "form": form,
            "summary": summary,
            "summary_formation": summary_formation,
            "summary_etude": summary_etude,
            "monthly": monthly,
            "top_clients": top_clients,
            "date_from": date_from,
            "date_to": date_to,
        },
    )


@admin_required
def outstanding_report(request):
    invoices = outstanding_invoices()
    from django.db.models import Sum

    total_outstanding = invoices.aggregate(total=Sum("amount_remaining"))[
        "total"
    ] or Decimal("0")
    return render(
        request,
        "financial/outstanding_report.html",
        {"invoices": invoices, "total_outstanding": total_outstanding},
    )


@admin_required
def expense_report(request):
    from django.db.models import Sum

    form = ReportFilterForm(request.GET or None)
    date_from, date_to = current_year_range()

    if form.is_valid():
        date_from, date_to = resolve_date_range(form.cleaned_data)

    qs = Expense.objects.filter(
        date__range=[date_from, date_to],
        approval_status=Expense.APPROVAL_APPROVED,
    )
    total = qs.aggregate(total=Sum("amount"))["total"] or Decimal("0")

    by_category = (
        qs.values("category__name").annotate(total=Sum("amount")).order_by("-total")
    )
    by_session = qs.filter(allocated_to_session__isnull=False).aggregate(
        total=Sum("amount")
    )["total"] or Decimal("0")
    by_project = qs.filter(allocated_to_project__isnull=False).aggregate(
        total=Sum("amount")
    )["total"] or Decimal("0")
    overhead = qs.filter(
        allocated_to_session__isnull=True, allocated_to_project__isnull=True
    ).aggregate(total=Sum("amount"))["total"] or Decimal("0")

    return render(
        request,
        "financial/expense_report.html",
        {
            "form": form,
            "total": total,
            "by_category": by_category,
            "by_session": by_session,
            "by_project": by_project,
            "overhead": overhead,
            "date_from": date_from,
            "date_to": date_to,
        },
    )


@admin_required
def margin_report(request):
    from formations.models import Session

    form = ReportFilterForm(request.GET or None)
    date_from, date_to = current_year_range()

    if form.is_valid():
        date_from, date_to = resolve_date_range(form.cleaned_data)

    completed_sessions = Session.objects.filter(
        status=Session.STATUS_COMPLETED,
        date_start__gte=date_from,
        date_end__lte=date_to,
    ).select_related("formation", "client")

    session_margins = [{"session": s, **session_margin(s)} for s in completed_sessions]

    from etudes.models import StudyProject

    projects = StudyProject.objects.filter(
        status=StudyProject.STATUS_COMPLETED,
        actual_end_date__range=[date_from, date_to],
    ).select_related("client")

    project_margins = [
        {
            "project": p,
            "budget": p.budget,
            "expenses": p.total_expenses,
            "margin": p.margin,
            "margin_rate": p.margin_rate,
        }
        for p in projects
    ]

    return render(
        request,
        "financial/margin_report.html",
        {
            "form": form,
            "session_margins": session_margins,
            "project_margins": project_margins,
            "date_from": date_from,
            "date_to": date_to,
        },
    )


@admin_required
def revenue_chart_data(request):
    """AJAX — monthly revenue breakdown for charting."""
    form = ReportFilterForm(request.GET or None)
    date_from, date_to = current_year_range()

    if form.is_valid():
        date_from, date_to = resolve_date_range(form.cleaned_data)

    monthly = revenue_by_month(date_from, date_to)
    # Convert Decimal to float for JSON serialisation
    payload = [
        {
            "month": row["month"],
            "formation_ht": float(row["formation_ht"]),
            "etude_ht": float(row["etude_ht"]),
            "total_ht": float(row["total_ht"]),
        }
        for row in monthly
    ]
    return JsonResponse({"data": payload})
