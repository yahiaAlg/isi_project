"""
Views for clients app - function-based views.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q

from .models import Client
from .forms import ClientForm


@login_required
def client_list(request):
    """List all clients - accessible to both admin and receptionist."""
    query = request.GET.get('q', '')
    client_type = request.GET.get('type', '')
    
    clients = Client.objects.all()
    
    # Apply filters
    if query:
        clients = clients.filter(
            Q(name__icontains=query) |
            Q(email__icontains=query) |
            Q(phone__icontains=query) |
            Q(contact_name__icontains=query)
        )
    
    if client_type:
        clients = clients.filter(client_type=client_type)
    
    return render(request, 'clients/client_list.html', {
        'clients': clients,
        'query': query,
        'client_type': client_type
    })


@login_required
def client_detail(request, client_id):
    """View client details - accessible to both admin and receptionist."""
    client = get_object_or_404(Client, id=client_id)
    
    # Get related data
    from formations.models import Session
    from etudes.models import StudyProject
    from financial.models import Invoice
    
    sessions = Session.objects.filter(client=client).order_by('-date_start')[:5]
    projects = StudyProject.objects.filter(client=client).order_by('-start_date')[:5]
    invoices = Invoice.objects.filter(client=client).order_by('-date')[:5]
    
    return render(request, 'clients/client_detail.html', {
        'client': client,
        'sessions': sessions,
        'projects': projects,
        'invoices': invoices
    })


@login_required
def client_create(request):
    """Create a new client - accessible to both admin and receptionist."""
    if request.method == 'POST':
        form = ClientForm(request.POST)
        if form.is_valid():
            client = form.save()
            messages.success(request, f"Le client '{client.name}' a été créé avec succès.")
            return redirect('clients:client_detail', client_id=client.id)
        else:
            messages.error(request, "Veuillez corriger les erreurs ci-dessous.")
    else:
        form = ClientForm()
    
    return render(request, 'clients/client_form.html', {
        'form': form,
        'action': 'create'
    })


@login_required
def client_edit(request, client_id):
    """Edit an existing client - accessible to both admin and receptionist."""
    client = get_object_or_404(Client, id=client_id)
    
    if request.method == 'POST':
        form = ClientForm(request.POST, instance=client)
        if form.is_valid():
            client = form.save()
            messages.success(request, f"Le client '{client.name}' a été mis à jour avec succès.")
            return redirect('clients:client_detail', client_id=client.id)
        else:
            messages.error(request, "Veuillez corriger les erreurs ci-dessous.")
    else:
        form = ClientForm(instance=client)
    
    return render(request, 'clients/client_form.html', {
        'form': form,
        'client': client,
        'action': 'edit'
    })


@login_required
def client_delete(request, client_id):
    """Delete a client - admin only."""
    # Check if user is admin
    if not request.user.profile.is_admin:
        messages.error(request, "Vous n'avez pas la permission de supprimer des clients.")
        return redirect('clients:client_detail', client_id=client_id)
    
    client = get_object_or_404(Client, id=client_id)
    
    if request.method == 'POST':
        client_name = client.name
        client.delete()
        messages.success(request, f"Le client '{client_name}' a été supprimé avec succès.")
        return redirect('clients:client_list')
    
    return render(request, 'clients/client_confirm_delete.html', {'client': client})
