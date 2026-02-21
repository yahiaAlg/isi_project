"""
Views for etudes app - function-based views.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Q

from .models import StudyProject, ProjectPhase, ProjectDeliverable
from .forms import (
    StudyProjectForm, ProjectPhaseForm, 
    ProjectDeliverableForm, ProjectStatusForm
)


# ==================== PROJECT VIEWS ====================

@login_required
def project_list(request):
    """List all study projects - accessible to both roles."""
    status = request.GET.get('status', '')
    client_id = request.GET.get('client', '')
    
    projects = StudyProject.objects.select_related('client').annotate(
        phase_count=Count('phases')
    ).order_by('-start_date')
    
    # Apply filters
    if status:
        projects = projects.filter(status=status)
    
    if client_id:
        projects = projects.filter(client_id=client_id)
    
    # Get clients for filter dropdown
    from clients.models import Client
    clients = Client.objects.all()
    
    return render(request, 'etudes/project_list.html', {
        'projects': projects,
        'clients': clients,
        'status_filter': status,
        'client_filter': client_id
    })


@login_required
def project_detail(request, project_id):
    """View project details - accessible to both roles."""
    project = get_object_or_404(
        StudyProject.objects.select_related('client'),
        id=project_id
    )
    
    phases = project.phases.all()
    
    # Get related invoice if exists
    from financial.models import Invoice
    try:
        invoice = Invoice.objects.filter(
            project=project,
            invoice_type=Invoice.TYPE_ETUDE
        ).first()
    except:
        invoice = None
    
    # Get related expenses
    from financial.models import Expense
    expenses = Expense.objects.filter(allocated_to_project=project)
    
    return render(request, 'etudes/project_detail.html', {
        'project': project,
        'phases': phases,
        'invoice': invoice,
        'expenses': expenses
    })


@login_required
def project_create(request):
    """Create a new study project - accessible to both roles."""
    if request.method == 'POST':
        form = StudyProjectForm(request.POST)
        if form.is_valid():
            project = form.save()
            messages.success(request, f"Le projet '{project.title}' a été créé avec succès.")
            return redirect('etudes:project_detail', project_id=project.id)
        else:
            messages.error(request, "Veuillez corriger les erreurs ci-dessous.")
    else:
        # Pre-populate from GET params if provided
        initial = {}
        if 'client' in request.GET:
            initial['client'] = request.GET.get('client')
        form = StudyProjectForm(initial=initial)
    
    return render(request, 'etudes/project_form.html', {
        'form': form,
        'action': 'create'
    })


@login_required
def project_edit(request, project_id):
    """Edit an existing project - admin only."""
    if not request.user.profile.is_admin:
        messages.error(request, "Vous n'avez pas la permission de modifier des projets.")
        return redirect('etudes:project_detail', project_id=project_id)
    
    project = get_object_or_404(StudyProject, id=project_id)
    
    if request.method == 'POST':
        form = StudyProjectForm(request.POST, instance=project)
        if form.is_valid():
            project = form.save()
            messages.success(request, f"Le projet '{project.title}' a été mis à jour avec succès.")
            return redirect('etudes:project_detail', project_id=project.id)
        else:
            messages.error(request, "Veuillez corriger les erreurs ci-dessous.")
    else:
        form = StudyProjectForm(instance=project)
    
    return render(request, 'etudes/project_form.html', {
        'form': form,
        'project': project,
        'action': 'edit'
    })


@login_required
def project_status_update(request, project_id):
    """Update project status - admin only."""
    if not request.user.profile.is_admin:
        messages.error(request, "Vous n'avez pas la permission de modifier le statut des projets.")
        return redirect('etudes:project_detail', project_id=project_id)
    
    project = get_object_or_404(StudyProject, id=project_id)
    
    if request.method == 'POST':
        form = ProjectStatusForm(request.POST, instance=project)
        if form.is_valid():
            # Check if trying to close project
            new_status = form.cleaned_data.get('status')
            if new_status == StudyProject.STATUS_COMPLETED:
                if not project.can_be_closed():
                    messages.error(
                        request, 
                        "Impossible de clôturer le projet : toutes les phases doivent être terminées."
                    )
                    return redirect('etudes:project_detail', project_id=project_id)
            
            form.save()
            messages.success(request, f"Le statut du projet a été mis à jour.")
            return redirect('etudes:project_detail', project_id=project.id)
    
    return redirect('etudes:project_detail', project_id=project_id)


# ==================== PHASE VIEWS ====================

@login_required
def phase_add(request, project_id):
    """Add a phase to a project - admin only."""
    if not request.user.profile.is_admin:
        messages.error(request, "Vous n'avez pas la permission d'ajouter des phases.")
        return redirect('etudes:project_detail', project_id=project_id)
    
    project = get_object_or_404(StudyProject, id=project_id)
    
    if request.method == 'POST':
        form = ProjectPhaseForm(request.POST)
        if form.is_valid():
            phase = form.save(commit=False)
            phase.project = project
            phase.save()
            messages.success(request, f"La phase '{phase.name}' a été ajoutée avec succès.")
            return redirect('etudes:project_detail', project_id=project_id)
        else:
            messages.error(request, "Veuillez corriger les erreurs ci-dessous.")
    else:
        # Auto-calculate next order
        next_order = project.phases.count() + 1
        form = ProjectPhaseForm(initial={'order': next_order})
    
    return render(request, 'etudes/phase_form.html', {
        'form': form,
        'project': project,
        'action': 'add'
    })


@login_required
def phase_edit(request, phase_id):
    """Edit a phase - admin only."""
    if not request.user.profile.is_admin:
        messages.error(request, "Vous n'avez pas la permission de modifier des phases.")
        phase = get_object_or_404(ProjectPhase, id=phase_id)
        return redirect('etudes:project_detail', project_id=phase.project.id)
    
    phase = get_object_or_404(ProjectPhase, id=phase_id)
    
    if request.method == 'POST':
        form = ProjectPhaseForm(request.POST, instance=phase)
        if form.is_valid():
            phase = form.save()
            messages.success(request, f"La phase '{phase.name}' a été mise à jour avec succès.")
            return redirect('etudes:project_detail', project_id=phase.project.id)
        else:
            messages.error(request, "Veuillez corriger les erreurs ci-dessous.")
    else:
        form = ProjectPhaseForm(instance=phase)
    
    return render(request, 'etudes/phase_form.html', {
        'form': form,
        'phase': phase,
        'project': phase.project,
        'action': 'edit'
    })


@login_required
def phase_status_update(request, phase_id):
    """Update phase status - admin only."""
    if not request.user.profile.is_admin:
        messages.error(request, "Vous n'avez pas la permission de modifier le statut des phases.")
        phase = get_object_or_404(ProjectPhase, id=phase_id)
        return redirect('etudes:project_detail', project_id=phase.project.id)
    
    phase = get_object_or_404(ProjectPhase, id=phase_id)
    
    if request.method == 'POST':
        status = request.POST.get('status')
        if status in [ProjectPhase.STATUS_IN_PROGRESS, ProjectPhase.STATUS_COMPLETED]:
            phase.status = status
            phase.save()
            messages.success(request, f"Le statut de la phase a été mis à jour.")
    
    return redirect('etudes:project_detail', project_id=phase.project.id)


# ==================== DELIVERABLE VIEWS ====================

@login_required
def deliverable_add(request, phase_id):
    """Add a deliverable to a phase - admin only."""
    if not request.user.profile.is_admin:
        messages.error(request, "Vous n'avez pas la permission d'ajouter des livrables.")
        phase = get_object_or_404(ProjectPhase, id=phase_id)
        return redirect('etudes:project_detail', project_id=phase.project.id)
    
    phase = get_object_or_404(ProjectPhase, id=phase_id)
    
    if request.method == 'POST':
        form = ProjectDeliverableForm(request.POST, request.FILES)
        if form.is_valid():
            deliverable = form.save(commit=False)
            deliverable.phase = phase
            deliverable.save()
            messages.success(request, f"Le livrable '{deliverable.title}' a été ajouté avec succès.")
            return redirect('etudes:project_detail', project_id=phase.project.id)
        else:
            messages.error(request, "Veuillez corriger les erreurs ci-dessous.")
    else:
        form = ProjectDeliverableForm()
    
    return render(request, 'etudes/deliverable_form.html', {
        'form': form,
        'phase': phase,
        'project': phase.project
    })


@login_required
def deliverable_view(request, deliverable_id):
    """View deliverable details - accessible to both roles."""
    deliverable = get_object_or_404(ProjectDeliverable, id=deliverable_id)
    
    return render(request, 'etudes/deliverable_detail.html', {
        'deliverable': deliverable,
        'phase': deliverable.phase,
        'project': deliverable.phase.project
    })
