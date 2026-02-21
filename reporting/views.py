"""
Views for reporting app - function-based views.
"""
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, Avg, Q
from django.utils import timezone
from datetime import timedelta
from calendar import month_name

from financial.models import Invoice, Payment, Expense
from formations.models import Session, Participant, Attestation
from etudes.models import StudyProject
from resources.models import Trainer, Equipment
from clients.models import Client


@login_required
def dashboard(request):
    """
    Main dashboard view.
    - Admin sees full dashboard with financials
    - Receptionist sees limited dashboard
    """
    is_admin = request.user.profile.is_admin
    
    # Common data for both roles
    today = timezone.now().date()
    current_month = today.month
    current_year = today.year
    
    # Upcoming sessions
    upcoming_sessions = Session.objects.filter(
        date_start__gte=today,
        status__in=[Session.STATUS_PLANNED, Session.STATUS_IN_PROGRESS]
    ).select_related('formation', 'client').order_by('date_start')[:5]
    
    # Active projects
    active_projects = StudyProject.objects.filter(
        status=StudyProject.STATUS_IN_PROGRESS
    ).select_related('client').order_by('-start_date')[:5]
    
    # Recent clients
    recent_clients = Client.objects.order_by('-created_at')[:5]
    
    context = {
        'upcoming_sessions': upcoming_sessions,
        'active_projects': active_projects,
        'recent_clients': recent_clients,
        'is_admin': is_admin,
    }
    
    # Admin-only data
    if is_admin:
        # Revenue summary
        invoices_this_month = Invoice.objects.filter(
            date__month=current_month,
            date__year=current_year,
            is_void=False
        )
        
        total_revenue_month = invoices_this_month.aggregate(
            total=Sum('amount_ttc')
        )['total'] or 0
        
        # Revenue by business line
        formation_revenue = invoices_this_month.filter(
            invoice_type=Invoice.TYPE_FORMATION
        ).aggregate(total=Sum('amount_ttc'))['total'] or 0
        
        etude_revenue = invoices_this_month.filter(
            invoice_type=Invoice.TYPE_ETUDE
        ).aggregate(total=Sum('amount_ttc'))['total'] or 0
        
        # Outstanding payments
        outstanding_invoices = Invoice.objects.filter(
            status__in=[Invoice.STATUS_UNPAID, Invoice.STATUS_PARTIALLY_PAID],
            is_void=False
        )
        total_outstanding = sum(inv.amount_remaining for inv in outstanding_invoices)
        overdue_count = sum(1 for inv in outstanding_invoices if inv.is_overdue)
        
        # Monthly trend (last 6 months)
        monthly_revenue = []
        for i in range(5, -1, -1):
            month_date = today - timedelta(days=30*i)
            month_invoices = Invoice.objects.filter(
                date__month=month_date.month,
                date__year=month_date.year,
                is_void=False
            )
            month_total = month_invoices.aggregate(total=Sum('amount_ttc'))['total'] or 0
            monthly_revenue.append({
                'month': month_name[month_date.month],
                'amount': month_total
            })
        
        # Session statistics
        sessions_this_month = Session.objects.filter(
            date_start__month=current_month,
            date_start__year=current_year
        )
        session_count = sessions_this_month.count()
        completed_sessions = sessions_this_month.filter(
            status=Session.STATUS_COMPLETED
        ).count()
        
        # Average fill rate
        avg_fill_rate = sessions_this_month.annotate(
            participant_count=Count('participants')
        ).aggregate(
            avg=Avg('participant_count')
        )['avg'] or 0
        
        # Top clients by revenue
        top_clients = Client.objects.annotate(
            total_revenue=Sum('invoices__amount_ttc', filter=Q(invoices__is_void=False))
        ).order_by('-total_revenue')[:5]
        
        # Trainer utilization
        trainer_stats = Trainer.objects.annotate(
            session_count=Count('sessions')
        ).order_by('-session_count')[:5]
        
        # Equipment alerts
        idle_equipment = Equipment.objects.filter(status=Equipment.STATUS_ACTIVE)
        idle_count = sum(1 for e in idle_equipment if e.is_idle)
        maintenance_due = sum(1 for e in Equipment.objects.all() if e.is_maintenance_due)
        
        context.update({
            'total_revenue_month': total_revenue_month,
            'formation_revenue': formation_revenue,
            'etude_revenue': etude_revenue,
            'total_outstanding': total_outstanding,
            'overdue_count': overdue_count,
            'monthly_revenue': monthly_revenue,
            'session_count': session_count,
            'completed_sessions': completed_sessions,
            'avg_fill_rate': avg_fill_rate,
            'top_clients': top_clients,
            'trainer_stats': trainer_stats,
            'idle_equipment_count': idle_count,
            'maintenance_due_count': maintenance_due,
        })
    
    return render(request, 'reporting/dashboard.html', context)


@login_required
def revenue_report(request):
    """Revenue report - admin only."""
    if not request.user.profile.is_admin:
        return redirect('reporting:dashboard')
    
    year = int(request.GET.get('year', timezone.now().year))
    
    # Annual revenue
    annual_invoices = Invoice.objects.filter(
        date__year=year,
        is_void=False
    )
    
    total_revenue = annual_invoices.aggregate(total=Sum('amount_ttc'))['total'] or 0
    total_ht = annual_invoices.aggregate(total=Sum('amount_ht'))['total'] or 0
    total_tva = annual_invoices.aggregate(total=Sum('amount_tva'))['total'] or 0
    
    # Monthly breakdown
    monthly_data = []
    for month in range(1, 13):
        month_invoices = annual_invoices.filter(date__month=month)
        formation = month_invoices.filter(invoice_type=Invoice.TYPE_FORMATION).aggregate(
            total=Sum('amount_ttc')
        )['total'] or 0
        etude = month_invoices.filter(invoice_type=Invoice.TYPE_ETUDE).aggregate(
            total=Sum('amount_ttc')
        )['total'] or 0
        monthly_data.append({
            'month': month_name[month],
            'formation': formation,
            'etude': etude,
            'total': formation + etude
        })
    
    # By business line
    formation_total = annual_invoices.filter(
        invoice_type=Invoice.TYPE_FORMATION
    ).aggregate(total=Sum('amount_ttc'))['total'] or 0
    
    etude_total = annual_invoices.filter(
        invoice_type=Invoice.TYPE_ETUDE
    ).aggregate(total=Sum('amount_ttc'))['total'] or 0
    
    return render(request, 'reporting/revenue_report.html', {
        'year': year,
        'total_revenue': total_revenue,
        'total_ht': total_ht,
        'total_tva': total_tva,
        'monthly_data': monthly_data,
        'formation_total': formation_total,
        'etude_total': etude_total,
    })


@login_required
def margins_report(request):
    """Margins report - admin only."""
    if not request.user.profile.is_admin:
        return redirect('reporting:dashboard')
    
    # Session margins
    sessions = Session.objects.filter(
        status=Session.STATUS_COMPLETED
    ).select_related('formation', 'client').annotate(
        participant_count=Count('participants')
    )
    
    session_margins = []
    for session in sessions[:20]:  # Last 20 sessions
        revenue = session.total_revenue
        # Get expenses for this session
        expenses = Expense.objects.filter(
            allocated_to_session=session
        ).aggregate(total=Sum('amount'))['total'] or 0
        # Trainer cost
        trainer_cost = 0
        if session.trainer:
            days = (session.date_end - session.date_start).days + 1
            trainer_cost = float(session.trainer.daily_rate) * days
        
        total_cost = expenses + trainer_cost
        margin = revenue - total_cost
        
        session_margins.append({
            'session': session,
            'revenue': revenue,
            'expenses': expenses,
            'trainer_cost': trainer_cost,
            'total_cost': total_cost,
            'margin': margin,
            'margin_percent': (margin / revenue * 100) if revenue > 0 else 0
        })
    
    # Project margins
    projects = StudyProject.objects.filter(
        status=StudyProject.STATUS_COMPLETED
    ).select_related('client')
    
    project_margins = []
    for project in projects[:20]:
        revenue = project.budget
        expenses = project.total_expenses
        margin = revenue - expenses
        
        project_margins.append({
            'project': project,
            'revenue': revenue,
            'expenses': expenses,
            'margin': margin,
            'margin_percent': (margin / revenue * 100) if revenue > 0 else 0
        })
    
    # Totals
    total_session_revenue = sum(s['revenue'] for s in session_margins)
    total_session_margin = sum(s['margin'] for s in session_margins)
    total_project_revenue = sum(p['revenue'] for p in project_margins)
    total_project_margin = sum(p['margin'] for p in project_margins)
    
    return render(request, 'reporting/margins_report.html', {
        'session_margins': session_margins,
        'project_margins': project_margins,
        'total_session_revenue': total_session_revenue,
        'total_session_margin': total_session_margin,
        'total_project_revenue': total_project_revenue,
        'total_project_margin': total_project_margin,
    })
