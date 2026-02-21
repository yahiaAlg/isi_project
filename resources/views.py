"""
Views for resources app - function-based views.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Sum, Q
from django.utils import timezone

from .models import Trainer, TrainingRoom, Equipment, EquipmentUsage, MaintenanceLog
from .forms import (
    TrainerForm, TrainingRoomForm, EquipmentForm,
    EquipmentUsageForm, MaintenanceLogForm
)


# ==================== TRAINER VIEWS ====================

@login_required
def trainer_list(request):
    """List all trainers - admin only."""
    if not request.user.profile.is_admin:
        messages.error(request, "Vous n'avez pas la permission d'accéder aux formateurs.")
        return redirect('reporting:dashboard')
    
    trainers = Trainer.objects.annotate(
        session_count=Count('sessions')
    ).order_by('last_name', 'first_name')
    
    return render(request, 'resources/trainer_list.html', {
        'trainers': trainers
    })


@login_required
def trainer_create(request):
    """Create a new trainer - admin only."""
    if not request.user.profile.is_admin:
        messages.error(request, "Vous n'avez pas la permission de créer des formateurs.")
        return redirect('reporting:dashboard')
    
    if request.method == 'POST':
        form = TrainerForm(request.POST)
        if form.is_valid():
            trainer = form.save()
            messages.success(request, f"Le formateur '{trainer.full_name}' a été créé avec succès.")
            return redirect('resources:trainer_list')
        else:
            messages.error(request, "Veuillez corriger les erreurs ci-dessous.")
    else:
        form = TrainerForm()
    
    return render(request, 'resources/trainer_form.html', {
        'form': form,
        'action': 'create'
    })


@login_required
def trainer_edit(request, trainer_id):
    """Edit an existing trainer - admin only."""
    if not request.user.profile.is_admin:
        messages.error(request, "Vous n'avez pas la permission de modifier des formateurs.")
        return redirect('reporting:dashboard')
    
    trainer = get_object_or_404(Trainer, id=trainer_id)
    
    if request.method == 'POST':
        form = TrainerForm(request.POST, instance=trainer)
        if form.is_valid():
            trainer = form.save()
            messages.success(request, f"Le formateur '{trainer.full_name}' a été mis à jour avec succès.")
            return redirect('resources:trainer_list')
        else:
            messages.error(request, "Veuillez corriger les erreurs ci-dessous.")
    else:
        form = TrainerForm(instance=trainer)
    
    return render(request, 'resources/trainer_form.html', {
        'form': form,
        'trainer': trainer,
        'action': 'edit'
    })


# ==================== ROOM VIEWS ====================

@login_required
def room_list(request):
    """List all training rooms - admin only."""
    if not request.user.profile.is_admin:
        messages.error(request, "Vous n'avez pas la permission d'accéder aux salles.")
        return redirect('reporting:dashboard')
    
    rooms = TrainingRoom.objects.annotate(
        session_count=Count('sessions')
    ).order_by('name')
    
    return render(request, 'resources/room_list.html', {
        'rooms': rooms
    })


@login_required
def room_create(request):
    """Create a new training room - admin only."""
    if not request.user.profile.is_admin:
        messages.error(request, "Vous n'avez pas la permission de créer des salles.")
        return redirect('reporting:dashboard')
    
    if request.method == 'POST':
        form = TrainingRoomForm(request.POST)
        if form.is_valid():
            room = form.save()
            messages.success(request, f"La salle '{room.name}' a été créée avec succès.")
            return redirect('resources:room_list')
        else:
            messages.error(request, "Veuillez corriger les erreurs ci-dessous.")
    else:
        form = TrainingRoomForm()
    
    return render(request, 'resources/room_form.html', {
        'form': form,
        'action': 'create'
    })


@login_required
def room_edit(request, room_id):
    """Edit an existing training room - admin only."""
    if not request.user.profile.is_admin:
        messages.error(request, "Vous n'avez pas la permission de modifier des salles.")
        return redirect('reporting:dashboard')
    
    room = get_object_or_404(TrainingRoom, id=room_id)
    
    if request.method == 'POST':
        form = TrainingRoomForm(request.POST, instance=room)
        if form.is_valid():
            room = form.save()
            messages.success(request, f"La salle '{room.name}' a été mise à jour avec succès.")
            return redirect('resources:room_list')
        else:
            messages.error(request, "Veuillez corriger les erreurs ci-dessous.")
    else:
        form = TrainingRoomForm(instance=room)
    
    return render(request, 'resources/room_form.html', {
        'form': form,
        'room': room,
        'action': 'edit'
    })


# ==================== EQUIPMENT VIEWS ====================

@login_required
def equipment_list(request):
    """List all equipment - admin only."""
    if not request.user.profile.is_admin:
        messages.error(request, "Vous n'avez pas la permission d'accéder aux équipements.")
        return redirect('reporting:dashboard')
    
    category = request.GET.get('category', '')
    status = request.GET.get('status', '')
    
    equipment = Equipment.objects.annotate(
        usage_count=Count('usages')
    ).order_by('category', 'name')
    
    # Apply filters
    if category:
        equipment = equipment.filter(category=category)
    
    if status:
        equipment = equipment.filter(status=status)
    
    # Get categories for filter
    categories = Equipment.objects.values_list('category', flat=True).distinct()
    
    return render(request, 'resources/equipment_list.html', {
        'equipment_list': equipment,
        'categories': categories,
        'category_filter': category,
        'status_filter': status
    })


@login_required
def equipment_detail(request, equipment_id):
    """View equipment details - admin only."""
    if not request.user.profile.is_admin:
        messages.error(request, "Vous n'avez pas la permission d'accéder aux équipements.")
        return redirect('reporting:dashboard')
    
    equipment = get_object_or_404(
        Equipment.objects.prefetch_related('usages', 'maintenance_logs'),
        id=equipment_id
    )
    
    usages = equipment.usages.all()[:10]
    maintenances = equipment.maintenance_logs.all()[:10]
    
    return render(request, 'resources/equipment_detail.html', {
        'equipment': equipment,
        'usages': usages,
        'maintenances': maintenances
    })


@login_required
def equipment_create(request):
    """Create new equipment - admin only."""
    if not request.user.profile.is_admin:
        messages.error(request, "Vous n'avez pas la permission de créer des équipements.")
        return redirect('reporting:dashboard')
    
    if request.method == 'POST':
        form = EquipmentForm(request.POST)
        if form.is_valid():
            equipment = form.save()
            messages.success(request, f"L'équipement '{equipment.name}' a été créé avec succès.")
            return redirect('resources:equipment_detail', equipment_id=equipment.id)
        else:
            messages.error(request, "Veuillez corriger les erreurs ci-dessous.")
    else:
        form = EquipmentForm()
    
    return render(request, 'resources/equipment_form.html', {
        'form': form,
        'action': 'create'
    })


@login_required
def equipment_edit(request, equipment_id):
    """Edit existing equipment - admin only."""
    if not request.user.profile.is_admin:
        messages.error(request, "Vous n'avez pas la permission de modifier des équipements.")
        return redirect('reporting:dashboard')
    
    equipment = get_object_or_404(Equipment, id=equipment_id)
    
    if request.method == 'POST':
        form = EquipmentForm(request.POST, instance=equipment)
        if form.is_valid():
            equipment = form.save()
            messages.success(request, f"L'équipement '{equipment.name}' a été mis à jour avec succès.")
            return redirect('resources:equipment_detail', equipment_id=equipment.id)
        else:
            messages.error(request, "Veuillez corriger les erreurs ci-dessous.")
    else:
        form = EquipmentForm(instance=equipment)
    
    return render(request, 'resources/equipment_form.html', {
        'form': form,
        'equipment': equipment,
        'action': 'edit'
    })


# ==================== USAGE VIEWS ====================

@login_required
def usage_add(request, equipment_id):
    """Add equipment usage - admin only."""
    if not request.user.profile.is_admin:
        messages.error(request, "Vous n'avez pas la permission d'enregistrer des utilisations.")
        return redirect('reporting:dashboard')
    
    equipment = get_object_or_404(Equipment, id=equipment_id)
    
    if request.method == 'POST':
        form = EquipmentUsageForm(request.POST, equipment=equipment)
        if form.is_valid():
            usage = form.save()
            messages.success(request, "L'utilisation a été enregistrée avec succès.")
            return redirect('resources:equipment_detail', equipment_id=equipment_id)
        else:
            messages.error(request, "Veuillez corriger les erreurs ci-dessous.")
    else:
        form = EquipmentUsageForm(equipment=equipment)
    
    return render(request, 'resources/usage_form.html', {
        'form': form,
        'equipment': equipment
    })


# ==================== MAINTENANCE VIEWS ====================

@login_required
def maintenance_add(request, equipment_id):
    """Add maintenance log - admin only."""
    if not request.user.profile.is_admin:
        messages.error(request, "Vous n'avez pas la permission d'enregistrer des maintenances.")
        return redirect('reporting:dashboard')
    
    equipment = get_object_or_404(Equipment, id=equipment_id)
    
    if request.method == 'POST':
        form = MaintenanceLogForm(request.POST, equipment=equipment)
        if form.is_valid():
            maintenance = form.save()
            messages.success(request, "La maintenance a été enregistrée avec succès.")
            return redirect('resources:equipment_detail', equipment_id=equipment_id)
        else:
            messages.error(request, "Veuillez corriger les erreurs ci-dessous.")
    else:
        form = MaintenanceLogForm(equipment=equipment)
    
    return render(request, 'resources/maintenance_form.html', {
        'form': form,
        'equipment': equipment
    })


# ==================== REPORT VIEWS ====================

@login_required
def equipment_report(request):
    """Equipment utilization report - admin only."""
    if not request.user.profile.is_admin:
        messages.error(request, "Vous n'avez pas la permission d'accéder aux rapports.")
        return redirect('reporting:dashboard')
    
    equipment = Equipment.objects.annotate(
        usage_count=Count('usages'),
        total_maintenance=Sum('maintenance_logs__cost')
    ).order_by('category', 'name')
    
    # Calculate idle equipment
    idle_equipment = [e for e in equipment if e.is_idle]
    
    # Equipment needing maintenance
    maintenance_due = [e for e in equipment if e.is_maintenance_due]
    
    # Summary stats
    total_equipment = equipment.count()
    total_value = sum(e.current_value for e in equipment)
    total_maintenance_cost = sum(e.total_maintenance_cost for e in equipment)
    
    return render(request, 'resources/equipment_report.html', {
        'equipment_list': equipment,
        'idle_equipment': idle_equipment,
        'maintenance_due': maintenance_due,
        'total_equipment': total_equipment,
        'total_value': total_value,
        'total_maintenance_cost': total_maintenance_cost
    })
