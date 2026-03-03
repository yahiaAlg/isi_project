# clients/views.py  —  v3.0

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from clients.forms import ClientContactForm, ClientFilterForm, ClientForm
from clients.models import Client, ClientContact
from core.utils import admin_required, login_and_active_required


# ─────────────────────────────────────────────────────────────────────────── #
# Clients — CRUD
# ─────────────────────────────────────────────────────────────────────────── #


@login_and_active_required
def client_list(request):
    qs = Client.objects.all()
    form = ClientFilterForm(request.GET or None)

    if form.is_valid():
        q = form.cleaned_data.get("q")
        client_type = form.cleaned_data.get("client_type")
        is_active = form.cleaned_data.get("is_active")
        is_tva_exempt = form.cleaned_data.get("is_tva_exempt")

        if q:
            qs = qs.filter(
                Q(name__icontains=q)
                | Q(city__icontains=q)
                | Q(activity_sector__icontains=q)
                | Q(contact_name__icontains=q)
                | Q(nif__icontains=q)
                | Q(rc__icontains=q)
            )
        if client_type:
            qs = qs.filter(client_type=client_type)
        if is_active == "1":
            qs = qs.filter(is_active=True)
        elif is_active == "0":
            qs = qs.filter(is_active=False)
        if is_tva_exempt == "1":
            qs = qs.filter(is_tva_exempt=True)
        elif is_tva_exempt == "0":
            qs = qs.filter(is_tva_exempt=False)

        # has_balance filtering is computed via property — small dataset, acceptable
        has_balance = form.cleaned_data.get("has_balance")
        if has_balance == "yes":
            qs = [c for c in qs if c.has_outstanding_balance]
        elif has_balance == "no":
            qs = [c for c in qs if not c.has_outstanding_balance]

    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "clients/client_list.html",
        {"page_obj": page_obj, "filter_form": form},
    )


@login_and_active_required
def client_detail(request, pk):
    client = get_object_or_404(Client, pk=pk)
    contacts = client.contacts.all()
    return render(
        request,
        "clients/client_detail.html",
        {
            "client": client,
            "contacts": contacts,
            "missing_fields": client.missing_fields_for_invoice(),
        },
    )


@login_and_active_required
def client_create(request):
    form = ClientForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        client = form.save()
        messages.success(request, f"Client « {client.name} » créé avec succès.")
        return redirect("clients:client_detail", pk=client.pk)

    return render(
        request,
        "clients/client_form.html",
        {"form": form, "action": "Nouveau client"},
    )


@login_and_active_required
def client_edit(request, pk):
    client = get_object_or_404(Client, pk=pk)
    form = ClientForm(request.POST or None, instance=client)

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Client mis à jour.")
        return redirect("clients:client_detail", pk=pk)

    return render(
        request,
        "clients/client_form.html",
        {"form": form, "action": "Modifier", "client": client},
    )


@admin_required
def client_deactivate(request, pk):
    """Toggle active / inactive — soft delete rather than hard delete."""
    if request.method != "POST":
        return redirect("clients:client_detail", pk=pk)

    client = get_object_or_404(Client, pk=pk)
    client.is_active = not client.is_active
    client.save(update_fields=["is_active"])
    state = "activé" if client.is_active else "désactivé"
    messages.success(request, f"Client « {client.name} » {state}.")
    return redirect("clients:client_detail", pk=pk)


@admin_required
def client_delete(request, pk):
    """
    Permanently delete a client record.
    GET  → confirmation page showing any linked data.
    POST → delete and redirect to client list.
    Admin only.
    """
    client = get_object_or_404(Client, pk=pk)

    # Gather related counts so the confirmation page can warn the admin.
    from financial.models import Invoice
    from formations.models import Session
    from etudes.models import StudyProject

    invoice_count = Invoice.objects.filter(client=client).count()
    session_count = Session.objects.filter(client=client).count()
    project_count = StudyProject.objects.filter(client=client).count()

    has_related = invoice_count or session_count or project_count

    if request.method == "POST":
        name = client.name
        client.delete()
        messages.success(request, f"Client « {name} » supprimé définitivement.")
        return redirect("clients:client_list")

    return render(
        request,
        "clients/client_delete_confirm.html",
        {
            "client": client,
            "invoice_count": invoice_count,
            "session_count": session_count,
            "project_count": project_count,
            "has_related": has_related,
        },
    )


# ─────────────────────────────────────────────────────────────────────────── #
# Contacts — sub-resource
# ─────────────────────────────────────────────────────────────────────────── #


@login_and_active_required
def contact_add(request, client_pk):
    client = get_object_or_404(Client, pk=client_pk)
    form = ClientContactForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        contact = form.save(commit=False)
        contact.client = client
        contact.save()
        messages.success(request, "Contact ajouté.")
        return redirect("clients:client_detail", pk=client_pk)

    return render(
        request,
        "clients/contact_form.html",
        {"form": form, "client": client, "action": "Ajouter un contact"},
    )


@login_and_active_required
def contact_edit(request, client_pk, pk):
    client = get_object_or_404(Client, pk=client_pk)
    contact = get_object_or_404(ClientContact, pk=pk, client=client)
    form = ClientContactForm(request.POST or None, instance=contact)

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Contact mis à jour.")
        return redirect("clients:client_detail", pk=client_pk)

    return render(
        request,
        "clients/contact_form.html",
        {"form": form, "client": client, "action": "Modifier le contact"},
    )


@login_and_active_required
def contact_delete(request, client_pk, pk):
    if request.method != "POST":
        return redirect("clients:client_detail", pk=client_pk)

    contact = get_object_or_404(ClientContact, pk=pk, client_id=client_pk)
    contact.delete()
    messages.success(request, "Contact supprimé.")
    return redirect("clients:client_detail", pk=client_pk)


# ─────────────────────────────────────────────────────────────────────────── #
# Activity history  (admin only — shows financial data)
# ─────────────────────────────────────────────────────────────────────────── #


@admin_required
def client_history(request, pk):
    """
    Aggregate view of a client's FINALE invoices, sessions, and study projects.
    Proformas are excluded from the financial summary (no fiscal value).
    """
    client = get_object_or_404(Client, pk=pk)

    from financial.models import Invoice

    # Only finalized invoices carry fiscal / accounting value
    invoices = Invoice.objects.filter(
        client=client, phase=Invoice.Phase.FINALE
    ).order_by("-invoice_date")

    from formations.models import Session

    sessions = Session.objects.filter(client=client).order_by("-date_start")

    from etudes.models import StudyProject

    projects = StudyProject.objects.filter(client=client).order_by("-start_date")

    return render(
        request,
        "clients/client_history.html",
        {
            "client": client,
            "invoices": invoices,
            "sessions": sessions,
            "projects": projects,
        },
    )


# ─────────────────────────────────────────────────────────────────────────── #
# AJAX
# ─────────────────────────────────────────────────────────────────────────── #


@login_and_active_required
def client_search_ajax(request):
    """
    JSON list of active clients matching the 'q' query param.
    Returns client_type and is_tva_exempt so the invoice form can
    auto-adjust the TVA rate when a client is selected.
    """
    q = request.GET.get("q", "").strip()
    if len(q) < 2:
        return JsonResponse({"results": []})

    clients = Client.objects.filter(name__icontains=q, is_active=True).values(
        "id", "name", "city", "client_type", "is_tva_exempt"
    )[:20]
    return JsonResponse({"results": list(clients)})
