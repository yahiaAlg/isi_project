"""
Views for formations app - function-based views.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Q
from django.http import JsonResponse
from django.utils import timezone
from datetime import timedelta

from .models import Formation, Session, Participant, Attestation
from .forms import (
    FormationForm, SessionForm, SessionStatusForm, 
    ParticipantForm, AttestationForm
)


# ==================== FORMATION VIEWS ====================

@login_required
def formation_list(request):
    """List all formations in catalog - admin only for management."""
    formations = Formation.objects.annotate(
        session_count=Count('sessions')
    ).order_by('title')
    
    return render(request, 'formations/formation_list.html', {
        'formations': formations
    })


@login_required
def formation_create(request):
    """Create a new formation - admin only."""
    if not request.user.profile.is_admin:
        messages.error(request, "Vous n'avez pas la permission de gérer le catalogue des formations.")
        return redirect('formations:formation_list')
    
    if request.method == 'POST':
        form = FormationForm(request.POST)
        if form.is_valid():
            formation = form.save()
            messages.success(request, f"La formation '{formation.title}' a été créée avec succès.")
            return redirect('formations:formation_list')
        else:
            messages.error(request, "Veuillez corriger les erreurs ci-dessous.")
    else:
        form = FormationForm()
    
    return render(request, 'formations/formation_form.html', {
        'form': form,
        'action': 'create'
    })


@login_required
def formation_edit(request, formation_id):
    """Edit an existing formation - admin only."""
    if not request.user.profile.is_admin:
        messages.error(request, "Vous n'avez pas la permission de gérer le catalogue des formations.")
        return redirect('formations:formation_list')
    
    formation = get_object_or_404(Formation, id=formation_id)
    
    if request.method == 'POST':
        form = FormationForm(request.POST, instance=formation)
        if form.is_valid():
            formation = form.save()
            messages.success(request, f"La formation '{formation.title}' a été mise à jour avec succès.")
            return redirect('formations:formation_list')
        else:
            messages.error(request, "Veuillez corriger les erreurs ci-dessous.")
    else:
        form = FormationForm(instance=formation)
    
    return render(request, 'formations/formation_form.html', {
        'form': form,
        'formation': formation,
        'action': 'edit'
    })


# ==================== SESSION VIEWS ====================

@login_required
def session_list(request):
    """List all sessions - accessible to both roles."""
    status = request.GET.get('status', '')
    formation_id = request.GET.get('formation', '')
    
    sessions = Session.objects.select_related(
        'formation', 'trainer', 'room', 'client'
    ).annotate(
        participant_count=Count('participants')
    ).order_by('-date_start')
    
    # Apply filters
    if status:
        sessions = sessions.filter(status=status)
    
    if formation_id:
        sessions = sessions.filter(formation_id=formation_id)
    
    # Get formations for filter dropdown
    formations = Formation.objects.filter(is_active=True)
    
    return render(request, 'formations/session_list.html', {
        'sessions': sessions,
        'formations': formations,
        'status_filter': status,
        'formation_filter': formation_id
    })


@login_required
def session_detail(request, session_id):
    """View session details - accessible to both roles."""
    session = get_object_or_404(
        Session.objects.select_related('formation', 'trainer', 'room', 'client'),
        id=session_id
    )
    
    participants = session.participants.all()
    attestations = Attestation.objects.filter(session=session)
    
    # Get related invoice if exists
    from financial.models import Invoice
    try:
        invoice = Invoice.objects.filter(
            session=session,
            invoice_type=Invoice.TYPE_FORMATION
        ).first()
    except:
        invoice = None
    
    return render(request, 'formations/session_detail.html', {
        'session': session,
        'participants': participants,
        'attestations': attestations,
        'invoice': invoice
    })


@login_required
def session_create(request):
    """Create a new session - admin only."""
    if not request.user.profile.is_admin:
        messages.error(request, "Vous n'avez pas la permission de créer des sessions.")
        return redirect('formations:session_list')
    
    if request.method == 'POST':
        form = SessionForm(request.POST)
        if form.is_valid():
            session = form.save()
            messages.success(request, f"La session a été créée avec succès.")
            return redirect('formations:session_detail', session_id=session.id)
        else:
            messages.error(request, "Veuillez corriger les erreurs ci-dessous.")
    else:
        # Pre-populate from GET params if provided
        initial = {}
        if 'formation' in request.GET:
            initial['formation'] = request.GET.get('formation')
        form = SessionForm(initial=initial)
    
    return render(request, 'formations/session_form.html', {
        'form': form,
        'action': 'create'
    })


@login_required
def session_edit(request, session_id):
    """Edit an existing session - admin only."""
    if not request.user.profile.is_admin:
        messages.error(request, "Vous n'avez pas la permission de modifier des sessions.")
        return redirect('formations:session_detail', session_id=session_id)
    
    session = get_object_or_404(Session, id=session_id)
    
    if request.method == 'POST':
        form = SessionForm(request.POST, instance=session)
        if form.is_valid():
            session = form.save()
            messages.success(request, f"La session a été mise à jour avec succès.")
            return redirect('formations:session_detail', session_id=session.id)
        else:
            messages.error(request, "Veuillez corriger les erreurs ci-dessous.")
    else:
        form = SessionForm(instance=session)
    
    return render(request, 'formations/session_form.html', {
        'form': form,
        'session': session,
        'action': 'edit'
    })


@login_required
def session_status_update(request, session_id):
    """Update session status - admin only."""
    if not request.user.profile.is_admin:
        messages.error(request, "Vous n'avez pas la permission de modifier le statut des sessions.")
        return redirect('formations:session_detail', session_id=session_id)
    
    session = get_object_or_404(Session, id=session_id)
    
    if request.method == 'POST':
        form = SessionStatusForm(request.POST, instance=session)
        if form.is_valid():
            form.save()
            messages.success(request, f"Le statut de la session a été mis à jour.")
            return redirect('formations:session_detail', session_id=session.id)
    
    return redirect('formations:session_detail', session_id=session_id)


# ==================== PARTICIPANT VIEWS ====================

@login_required
def participant_add(request, session_id):
    """Add a participant to a session - accessible to both roles."""
    session = get_object_or_404(Session, id=session_id)
    
    # Check if session is full
    if session.is_full:
        messages.error(request, "Cette session est complète. Impossible d'ajouter plus de participants.")
        return redirect('formations:session_detail', session_id=session_id)
    
    if request.method == 'POST':
        form = ParticipantForm(request.POST)
        if form.is_valid():
            participant = form.save(commit=False)
            participant.session = session
            participant.save()
            messages.success(request, f"Le participant '{participant.full_name}' a été ajouté avec succès.")
            return redirect('formations:session_detail', session_id=session_id)
        else:
            messages.error(request, "Veuillez corriger les erreurs ci-dessous.")
    else:
        form = ParticipantForm()
    
    return render(request, 'formations/participant_form.html', {
        'form': form,
        'session': session,
        'action': 'add'
    })


@login_required
def participant_edit(request, participant_id):
    """Edit a participant - accessible to both roles."""
    participant = get_object_or_404(Participant, id=participant_id)
    
    if request.method == 'POST':
        form = ParticipantForm(request.POST, instance=participant)
        if form.is_valid():
            participant = form.save()
            messages.success(request, f"Le participant a été mis à jour avec succès.")
            return redirect('formations:session_detail', session_id=participant.session.id)
        else:
            messages.error(request, "Veuillez corriger les erreurs ci-dessous.")
    else:
        form = ParticipantForm(instance=participant)
    
    return render(request, 'formations/participant_form.html', {
        'form': form,
        'participant': participant,
        'session': participant.session,
        'action': 'edit'
    })


@login_required
def participant_remove(request, participant_id):
    """Remove a participant from a session - admin only."""
    if not request.user.profile.is_admin:
        messages.error(request, "Vous n'avez pas la permission de supprimer des participants.")
        participant = get_object_or_404(Participant, id=participant_id)
        return redirect('formations:session_detail', session_id=participant.session.id)
    
    participant = get_object_or_404(Participant, id=participant_id)
    session_id = participant.session.id
    
    if request.method == 'POST':
        participant_name = participant.full_name
        participant.delete()
        messages.success(request, f"Le participant '{participant_name}' a été supprimé avec succès.")
        return redirect('formations:session_detail', session_id=session_id)
    
    return render(request, 'formations/participant_confirm_delete.html', {
        'participant': participant
    })


# ==================== ATTESTATION VIEWS ====================

@login_required
def attestation_view(request, participant_id):
    """View/print attestation for a participant."""
    participant = get_object_or_404(Participant, id=participant_id)
    
    # Get or check for attestation
    attestation = Attestation.objects.filter(participant=participant).first()
    
    return render(request, 'formations/attestation_print.html', {
        'participant': participant,
        'attestation': attestation,
        'session': participant.session
    })


@login_required
def attestation_issue(request, participant_id):
    """Issue attestation for a single participant - admin only."""
    if not request.user.profile.is_admin:
        messages.error(request, "Vous n'avez pas la permission d'émettre des attestations.")
        participant = get_object_or_404(Participant, id=participant_id)
        return redirect('formations:session_detail', session_id=participant.session.id)
    
    participant = get_object_or_404(Participant, id=participant_id)
    
    # Check if session is completed
    if participant.session.status != Session.STATUS_COMPLETED:
        messages.error(request, "La session doit être terminée avant d'émettre des attestations.")
        return redirect('formations:session_detail', session_id=participant.session.id)
    
    # Check if already has attestation
    existing = Attestation.objects.filter(participant=participant).first()
    if existing:
        messages.info(request, "Une attestation existe déjà pour ce participant.")
        return redirect('formations:attestation_view', participant_id=participant.id)
    
    if request.method == 'POST':
        form = AttestationForm(request.POST, participant=participant)
        if form.is_valid():
            attestation = form.save(commit=False)
            attestation.participant = participant
            attestation.session = participant.session
            attestation.save()
            messages.success(request, f"L'attestation a été émise avec succès.")
            return redirect('formations:attestation_view', participant_id=participant.id)
        else:
            messages.error(request, "Veuillez corriger les erreurs ci-dessous.")
    else:
        form = AttestationForm(participant=participant)
    
    return render(request, 'formations/attestation_form.html', {
        'form': form,
        'participant': participant,
        'session': participant.session
    })


@login_required
def attestation_issue_all(request, session_id):
    """Issue attestations for all participants in a session - admin only."""
    if not request.user.profile.is_admin:
        messages.error(request, "Vous n'avez pas la permission d'émettre des attestations.")
        return redirect('formations:session_detail', session_id=session_id)
    
    session = get_object_or_404(Session, id=session_id)
    
    # Check if session is completed
    if session.status != Session.STATUS_COMPLETED:
        messages.error(request, "La session doit être terminée avant d'émettre des attestations.")
        return redirect('formations:session_detail', session_id=session_id)
    
    # Get participants without attestations
    participants = session.participants.filter(attestation__isnull=True)
    
    if request.method == 'POST':
        issue_date = request.POST.get('issue_date')
        if not issue_date:
            issue_date = timezone.now().date()
        
        count = 0
        for participant in participants:
            # Calculate validity
            from core.models import FormationInfo
            info = FormationInfo.get_instance()
            years = info.attestation_validity_years if info else 5
            valid_until = issue_date + timedelta(days=365 * years)
            
            Attestation.objects.create(
                participant=participant,
                session=session,
                issue_date=issue_date,
                valid_until=valid_until
            )
            count += 1
        
        messages.success(request, f"{count} attestation(s) ont été émises avec succès.")
        return redirect('formations:session_detail', session_id=session_id)
    
    return render(request, 'formations/attestation_issue_all.html', {
        'session': session,
        'participants': participants
    })
