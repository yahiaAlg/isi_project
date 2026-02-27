# clients/views.py

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from clients.forms import ClientContactForm, ClientFilterForm, ClientForm
from clients.models import Client, ClientContact
from core.utils import admin_required, login_and_active_required


# ---------------------------------------------------------------------------
# Clients — CRUD
# ---------------------------------------------------------------------------


@login_and_active_required
def client_list(request):
    qs = Client.objects.all()
    form = ClientFilterForm(request.GET or None)

    if form.is_valid():
        q = form.cleaned_data.get("q")
        client_type = form.cleaned_data.get("client_type")
        is_active = form.cleaned_data.get("is_active")

        if q:
            qs = qs.filter(
                Q(name__icontains=q)
                | Q(city__icontains=q)
                | Q(activity_sector__icontains=q)
                | Q(contact_name__icontains=q)
            )
        if client_type:
            qs = qs.filter(client_type=client_type)
        if is_active == "1":
            qs = qs.filter(is_active=True)
        elif is_active == "0":
            qs = qs.filter(is_active=False)

        # has_balance filtering is done in Python because outstanding_balance
        # is a property, not a DB annotation — small dataset, acceptable cost.
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
        {"client": client, "contacts": contacts},
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
        messages.success(request, "Client mis à jour avec succès.")
        return redirect("clients:client_detail", pk=pk)

    return render(
        request,
        "clients/client_form.html",
        {"form": form, "action": "Modifier", "client": client},
    )


@admin_required
def client_deactivate(request, pk):
    """Toggle active/inactive — soft delete rather than hard delete."""
    if request.method != "POST":
        return redirect("clients:client_detail", pk=pk)

    client = get_object_or_404(Client, pk=pk)
    client.is_active = not client.is_active
    client.save(update_fields=["is_active"])

    state = "activé" if client.is_active else "désactivé"
    messages.success(request, f"Client « {client.name} » {state}.")
    return redirect("clients:client_detail", pk=pk)


# ---------------------------------------------------------------------------
# Contacts — sub-resource
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Activity history
# ---------------------------------------------------------------------------


@admin_required
def client_history(request, pk):
    """
    Aggregate view of a client's invoices, sessions, and study projects.
    Financial data (invoices, payments) is admin-only per the spec.
    """
    client = get_object_or_404(Client, pk=pk)

    from financial.models import Invoice

    invoices = Invoice.objects.filter(client=client).order_by("-invoice_date")

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


# ---------------------------------------------------------------------------
# AJAX
# ---------------------------------------------------------------------------


@login_and_active_required
def client_search_ajax(request):
    """
    Returns a JSON list of active clients matching the 'q' query param.
    Used by select widgets in session / project / invoice forms.
    """
    q = request.GET.get("q", "").strip()
    if len(q) < 2:
        return JsonResponse({"results": []})

    clients = Client.objects.filter(name__icontains=q, is_active=True).values(
        "id", "name", "city", "client_type"
    )[:20]
    return JsonResponse({"results": list(clients)})
