"""
Comprehensive views for financial app.
"""
import csv
import io
from datetime import datetime, timedelta
from decimal import Decimal
from calendar import month_name

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Count, Q, F, Avg
from django.db import transaction
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST

from .models import (
    Invoice, InvoiceLineItem, Payment, AdvancePayment,
    Expense, ExpenseCategory, Vendor, Budget, FinancialTransaction
)
from .forms import (
    InvoiceForm, InvoiceLineItemFormSet, PaymentForm, PaymentReverseForm,
    InvoiceVoidForm, InvoiceSendForm, AdvancePaymentForm, AdvanceAllocationForm,
    ExpenseForm, ExpenseCategoryForm, VendorForm, ExpenseApprovalForm,
    ExpenseBulkActionForm, BudgetForm, FinancialReportFilterForm, DateRangeForm
)


# ============================================================================
# INVOICE VIEWS
# ============================================================================

@login_required
def invoice_list(request):
    """
    List all invoices with advanced filtering and pagination.
    """
    if not request.user.profile.is_admin:
        messages.error(request, "Vous n'avez pas la permission d'accéder aux factures.")
        return redirect('reporting:dashboard')
    
    # Get filter parameters
    invoice_type = request.GET.get('type', '')
    status = request.GET.get('status', '')
    client_id = request.GET.get('client', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    is_overdue = request.GET.get('overdue', '')
    search = request.GET.get('search', '')
    
    # Base queryset
    invoices = Invoice.objects.select_related(
        'client', 'session', 'project', 'created_by'
    ).prefetch_related('payments').order_by('-date', '-reference')
    
    # Apply filters
    if invoice_type:
        invoices = invoices.filter(invoice_type=invoice_type)
    
    if status:
        invoices = invoices.filter(status=status)
    
    if client_id:
        invoices = invoices.filter(client_id=client_id)
    
    if date_from:
        invoices = invoices.filter(date__gte=date_from)
    
    if date_to:
        invoices = invoices.filter(date__lte=date_to)
    
    if is_overdue == 'true':
        invoices = [inv for inv in invoices if inv.is_overdue]
    
    if search:
        invoices = invoices.filter(
            Q(reference__icontains=search) |
            Q(client__name__icontains=search) |
            Q(description__icontains=search)
        )
    
    # Calculate summary statistics
    summary = invoices.aggregate(
        total_count=Count('id'),
        total_ht=Sum('amount_ht'),
        total_ttc=Sum('amount_ttc'),
        total_paid=Sum('amount_paid')
    )
    
    summary['total_remaining'] = (
        (summary['total_ttc'] or Decimal('0')) - 
        (summary['total_paid'] or Decimal('0'))
    )
    
    # Pagination
    paginator = Paginator(invoices, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get filter options
    from clients.models import Client
    clients = Client.objects.all()
    
    context = {
        'page_obj': page_obj,
        'invoices': page_obj.object_list,
        'summary': summary,
        'clients': clients,
        'type_filter': invoice_type,
        'status_filter': status,
        'client_filter': client_id,
        'date_from': date_from,
        'date_to': date_to,
        'overdue_filter': is_overdue,
        'search': search,
        'status_choices': Invoice.STATUS_CHOICES,
        'type_choices': Invoice.TYPE_CHOICES,
    }
    
    return render(request, 'financial/invoice_list.html', context)


@login_required
def invoice_detail(request, invoice_id):
    """
    Detailed invoice view with payment history and actions.
    """
    if not request.user.profile.is_admin:
        messages.error(request, "Vous n'avez pas la permission d'accéder aux factures.")
        return redirect('reporting:dashboard')
    
    invoice = get_object_or_404(
        Invoice.objects.select_related(
            'client', 'session', 'project', 'created_by', 
            'voided_by', 'original_invoice'
        ).prefetch_related('line_items', 'payments', 'credit_notes'),
        id=invoice_id
    )
    
    payments = invoice.payments.filter(is_reversed=False).order_by('-date')
    line_items = invoice.line_items.order_by('order')
    
    # Get related data
    related_invoices = Invoice.objects.filter(
        client=invoice.client
    ).exclude(id=invoice.id).order_by('-date')[:5]
    
    context = {
        'invoice': invoice,
        'payments': payments,
        'line_items': line_items,
        'related_invoices': related_invoices,
        'can_be_voided': not invoice.is_void and not invoice.is_credit_note,
        'can_add_payment': invoice.status not in [
            Invoice.STATUS_PAID, Invoice.STATUS_CANCELLED
        ] and not invoice.is_void,
    }
    
    return render(request, 'financial/invoice_detail.html', context)


@login_required
def invoice_create(request):
    """
    Create new invoice with line items.
    """
    if not request.user.profile.is_admin:
        messages.error(request, "Vous n'avez pas la permission de créer des factures.")
        return redirect('reporting:dashboard')
    
    if request.method == 'POST':
        form = InvoiceForm(request.POST)
        formset = InvoiceLineItemFormSet(request.POST, prefix='line_items')
        
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                invoice = form.save(commit=False)
                invoice.created_by = request.user
                invoice.status = Invoice.STATUS_DRAFT
                invoice.save()
                
                # Save line items
                formset.instance = invoice
                formset.save()
                
                # Recalculate totals
                invoice.recalculate_totals()
                invoice.save()
                
                messages.success(
                    request, 
                    f"Facture {invoice.reference} créée avec succès. "
                    f"Montant TTC: {invoice.amount_ttc} DA"
                )
                return redirect('financial:invoice_detail', invoice_id=invoice.id)
        else:
            messages.error(request, "Veuillez corriger les erreurs ci-dessous.")
    else:
        form = InvoiceForm()
        formset = InvoiceLineItemFormSet(prefix='line_items')
    
    context = {
        'form': form,
        'formset': formset,
        'action': 'create'
    }
    
    return render(request, 'financial/invoice_form.html', context)


@login_required
def invoice_create_from_session(request, session_id):
    """
    Create invoice from completed session with pre-populated data.
    """
    if not request.user.profile.is_admin:
        messages.error(request, "Vous n'avez pas la permission de créer des factures.")
        return redirect('reporting:dashboard')
    
    from formations.models import Session
    session = get_object_or_404(Session, id=session_id)
    
    # Validate session can be invoiced
    if not session.can_be_invoiced:
        messages.error(request, "Cette session ne peut pas être facturée (doit être terminée).")
        return redirect('formations:session_detail', session_id=session_id)
    
    # Check for existing invoice
    existing = Invoice.objects.filter(
        session=session, 
        invoice_type=Invoice.TYPE_FORMATION,
        is_void=False
    ).first()
    
    if existing:
        messages.info(request, "Une facture existe déjà pour cette session.")
        return redirect('financial:invoice_detail', invoice_id=existing.id)
    
    if request.method == 'POST':
        form = InvoiceForm(request.POST)
        formset = InvoiceLineItemFormSet(request.POST, prefix='line_items')
        
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                invoice = form.save(commit=False)
                invoice.created_by = request.user
                invoice.save()
                
                formset.instance = invoice
                formset.save()
                
                invoice.recalculate_totals()
                invoice.save()
                
                messages.success(request, f"Facture {invoice.reference} créée avec succès.")
                return redirect('financial:invoice_detail', invoice_id=invoice.id)
        else:
            messages.error(request, "Veuillez corriger les erreurs ci-dessous.")
    else:
        # Pre-populate from session
        price = session.price_per_participant or session.formation.base_price
        
        initial = {
            'invoice_type': Invoice.TYPE_FORMATION,
            'client': session.client.id if session.client else None,
            'session': session.id,
            'tva_rate': Decimal('0.1900'),
            'header_notes': f"Formation: {session.formation.title}",
            'footer_notes': f"Session du {session.date_start} au {session.date_end}",
        }
        form = InvoiceForm(initial=initial)
        
        # Create initial line item
        from django.forms.models import inlineformset_factory
        LineItemFormSet = inlineformset_factory(
            Invoice, InvoiceLineItem, 
            fields=['description', 'quantity', 'unit', 'unit_price', 'tva_rate'],
            extra=1
        )
        
        line_initial = [{
            'description': f"Formation: {session.formation.title}\n{session.formation.description}",
            'quantity': session.participant_count,
            'unit': 'participant',
            'unit_price': price,
            'tva_rate': Decimal('0.1900'),
        }]
        formset = InvoiceLineItemFormSet(prefix='line_items', initial=line_initial)
    
    context = {
        'form': form,
        'formset': formset,
        'session': session,
        'action': 'create_from_session'
    }
    
    return render(request, 'financial/invoice_form.html', context)


@login_required
def invoice_create_from_project(request, project_id):
    """
    Create invoice from study project.
    """
    if not request.user.profile.is_admin:
        messages.error(request, "Vous n'avez pas la permission de créer des factures.")
        return redirect('reporting:dashboard')
    
    from etudes.models import StudyProject
    project = get_object_or_404(StudyProject, id=project_id)
    
    # Check for existing invoice
    existing = Invoice.objects.filter(
        project=project,
        invoice_type=Invoice.TYPE_ETUDE,
        is_void=False
    ).first()
    
    if existing:
        messages.info(request, "Une facture existe déjà pour ce projet.")
        return redirect('financial:invoice_detail', invoice_id=existing.id)
    
    if request.method == 'POST':
        form = InvoiceForm(request.POST)
        formset = InvoiceLineItemFormSet(request.POST, prefix='line_items')
        
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                invoice = form.save(commit=False)
                invoice.created_by = request.user
                invoice.save()
                
                formset.instance = invoice
                formset.save()
                
                invoice.recalculate_totals()
                invoice.save()
                
                messages.success(request, f"Facture {invoice.reference} créée avec succès.")
                return redirect('financial:invoice_detail', invoice_id=invoice.id)
        else:
            messages.error(request, "Veuillez corriger les erreurs ci-dessous.")
    else:
        initial = {
            'invoice_type': Invoice.TYPE_ETUDE,
            'client': project.client.id,
            'project': project.id,
            'tva_rate': Decimal('0.1900'),
            'header_notes': f"Étude: {project.title}",
            'footer_notes': f"Projet démarré le {project.start_date}",
        }
        form = InvoiceForm(initial=initial)
        
        line_initial = [{
            'description': f"Étude: {project.title}\n{project.description}",
            'quantity': 1,
            'unit': 'forfait',
            'unit_price': project.budget,
            'tva_rate': Decimal('0.1900'),
        }]
        formset = InvoiceLineItemFormSet(prefix='line_items', initial=line_initial)
    
    context = {
        'form': form,
        'formset': formset,
        'project': project,
        'action': 'create_from_project'
    }
    
    return render(request, 'financial/invoice_form.html', context)


@login_required
def invoice_edit(request, invoice_id):
    """
    Edit draft invoice.
    """
    if not request.user.profile.is_admin:
        messages.error(request, "Vous n'avez pas la permission de modifier des factures.")
        return redirect('reporting:dashboard')
    
    invoice = get_object_or_404(Invoice, id=invoice_id)
    
    # Only draft invoices can be edited
    if invoice.status != Invoice.STATUS_DRAFT:
        messages.error(request, "Seules les factures en brouillon peuvent être modifiées.")
        return redirect('financial:invoice_detail', invoice_id=invoice_id)
    
    if request.method == 'POST':
        form = InvoiceForm(request.POST, instance=invoice)
        formset = InvoiceLineItemFormSet(request.POST, instance=invoice, prefix='line_items')
        
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                invoice = form.save()
                formset.save()
                invoice.recalculate_totals()
                invoice.save()
                
                messages.success(request, f"Facture {invoice.reference} mise à jour avec succès.")
                return redirect('financial:invoice_detail', invoice_id=invoice.id)
        else:
            messages.error(request, "Veuillez corriger les erreurs ci-dessous.")
    else:
        form = InvoiceForm(instance=invoice)
        formset = InvoiceLineItemFormSet(instance=invoice, prefix='line_items')
    
    context = {
        'form': form,
        'formset': formset,
        'invoice': invoice,
        'action': 'edit'
    }
    
    return render(request, 'financial/invoice_form.html', context)


@login_required
def invoice_send(request, invoice_id):
    """
    Mark invoice as sent to client.
    """
    if not request.user.profile.is_admin:
        messages.error(request, "Permission refusée.")
        return redirect('reporting:dashboard')
    
    invoice = get_object_or_404(Invoice, id=invoice_id)
    
    if invoice.status != Invoice.STATUS_DRAFT:
        messages.error(request, "Cette facture a déjà été envoyée.")
        return redirect('financial:invoice_detail', invoice_id=invoice_id)
    
    if request.method == 'POST':
        form = InvoiceSendForm(request.POST)
        if form.is_valid():
            invoice.sent_date = form.cleaned_data['sent_date']
            invoice.status = Invoice.STATUS_SENT
            invoice.save()
            
            messages.success(
                request, 
                f"Facture {invoice.reference} marquée comme envoyée le {invoice.sent_date}."
            )
            return redirect('financial:invoice_detail', invoice_id=invoice_id)
    else:
        form = InvoiceSendForm()
    
    context = {
        'form': form,
        'invoice': invoice
    }
    
    return render(request, 'financial/invoice_send_form.html', context)


@login_required
def invoice_print(request, invoice_id):
    """
    Printable invoice view.
    """
    if not request.user.profile.is_admin:
        messages.error(request, "Permission refusée.")
        return redirect('reporting:dashboard')
    
    invoice = get_object_or_404(
        Invoice.objects.select_related('client', 'session', 'project'),
        id=invoice_id
    )
    
    line_items = invoice.line_items.order_by('order')
    payments = invoice.payments.filter(is_reversed=False)
    
    context = {
        'invoice': invoice,
        'line_items': line_items,
        'payments': payments,
        'print_mode': True
    }
    
    return render(request, 'financial/invoice_print.html', context)


@login_required
def invoice_void(request, invoice_id):
    """
    Void invoice and optionally create credit note.
    """
    if not request.user.profile.is_admin:
        messages.error(request, "Permission refusée.")
        return redirect('reporting:dashboard')
    
    invoice = get_object_or_404(Invoice, id=invoice_id)
    
    if invoice.is_void or invoice.is_credit_note:
        messages.error(request, "Cette facture ne peut pas être annulée.")
        return redirect('financial:invoice_detail', invoice_id=invoice_id)
    
    if request.method == 'POST':
        form = InvoiceVoidForm(request.POST, instance=invoice)
        if form.is_valid():
            with transaction.atomic():
                create_credit_note = form.cleaned_data.get('create_credit_note', True)
                reason = form.cleaned_data['void_reason']
                
                if create_credit_note:
                    credit_note = invoice.create_credit_note(reason, request.user)
                    messages.success(
                        request,
                        f"Facture {invoice.reference} annulée. Avoir {credit_note.reference} créé."
                    )
                else:
                    invoice.is_void = True
                    invoice.void_date = timezone.now().date()
                    invoice.void_reason = reason
                    invoice.voided_by = request.user
                    invoice.status = Invoice.STATUS_CANCELLED
                    invoice.save()
                    messages.success(
                        request,
                        f"Facture {invoice.reference} annulée sans avoir."
                    )
                
                return redirect('financial:invoice_detail', invoice_id=invoice_id)
    else:
        form = InvoiceVoidForm()
    
    context = {
        'form': form,
        'invoice': invoice
    }
    
    return render(request, 'financial/invoice_void_form.html', context)


# ============================================================================
# PAYMENT VIEWS
# ============================================================================

@login_required
def payment_add(request, invoice_id):
    """
    Add payment to invoice.
    """
    if not request.user.profile.is_admin:
        messages.error(request, "Permission refusée.")
        return redirect('reporting:dashboard')
    
    invoice = get_object_or_404(Invoice, id=invoice_id)
    
    if invoice.is_void:
        messages.error(request, "Impossible d'ajouter un paiement à une facture annulée.")
        return redirect('financial:invoice_detail', invoice_id=invoice_id)
    
    if invoice.status == Invoice.STATUS_PAID:
        messages.error(request, "Cette facture est déjà entièrement payée.")
        return redirect('financial:invoice_detail', invoice_id=invoice_id)
    
    if request.method == 'POST':
        form = PaymentForm(request.POST, request.FILES, invoice=invoice)
        if form.is_valid():
            payment = form.save(commit=False)
            payment.invoice = invoice
            payment.recorded_by = request.user
            payment.save()
            
            messages.success(
                request,
                f"Paiement de {payment.amount} DA enregistré. "
                f"Solde restant: {invoice.amount_remaining} DA"
            )
            return redirect('financial:invoice_detail', invoice_id=invoice_id)
    else:
        # Pre-fill with remaining amount
        form = PaymentForm(invoice=invoice, initial={
            'amount': invoice.amount_remaining
        })
    
    context = {
        'form': form,
        'invoice': invoice
    }
    
    return render(request, 'financial/payment_form.html', context)


@login_required
def payment_reverse(request, payment_id):
    """
    Reverse a payment.
    """
    if not request.user.profile.is_admin:
        messages.error(request, "Permission refusée.")
        return redirect('reporting:dashboard')
    
    payment = get_object_or_404(Payment, id=payment_id)
    invoice_id = payment.invoice.id
    
    if payment.is_reversed:
        messages.error(request, "Ce paiement est déjà annulé.")
        return redirect('financial:invoice_detail', invoice_id=invoice_id)
    
    if request.method == 'POST':
        form = PaymentReverseForm(request.POST)
        if form.is_valid():
            reason = form.cleaned_data['reason']
            payment.reverse(request.user, reason)
            
            messages.success(request, "Paiement annulé avec succès.")
            return redirect('financial:invoice_detail', invoice_id=invoice_id)
    else:
        form = PaymentReverseForm()
    
    context = {
        'form': form,
        'payment': payment
    }
    
    return render(request, 'financial/payment_reverse_form.html', context)


# ============================================================================
# ADVANCE PAYMENT VIEWS
# ============================================================================

@login_required
def advance_payment_list(request):
    """
    List all advance payments.
    """
    if not request.user.profile.is_admin:
        messages.error(request, "Permission refusée.")
        return redirect('reporting:dashboard')
    
    advances = AdvancePayment.objects.select_related(
        'client', 'allocated_to_invoice', 'recorded_by'
    ).order_by('-date')
    
    # Summary
    total_advances = advances.aggregate(total=Sum('amount'))['total'] or Decimal('0')
    total_allocated = advances.aggregate(total=Sum('allocated_amount'))['total'] or Decimal('0')
    total_remaining = total_advances - total_allocated
    
    context = {
        'advances': advances,
        'total_advances': total_advances,
        'total_allocated': total_allocated,
        'total_remaining': total_remaining
    }
    
    return render(request, 'financial/advance_payment_list.html', context)


@login_required
def advance_payment_create(request):
    """
    Create new advance payment.
    """
    if not request.user.profile.is_admin:
        messages.error(request, "Permission refusée.")
        return redirect('reporting:dashboard')
    
    if request.method == 'POST':
        form = AdvancePaymentForm(request.POST)
        if form.is_valid():
            advance = form.save(commit=False)
            advance.recorded_by = request.user
            advance.save()
            
            messages.success(
                request,
                f"Acompte de {advance.amount} DA enregistré pour {advance.client.name}."
            )
            return redirect('financial:advance_payment_list')
    else:
        form = AdvancePaymentForm()
    
    context = {
        'form': form
    }
    
    return render(request, 'financial/advance_payment_form.html', context)


@login_required
def advance_payment_allocate(request, advance_id):
    """
    Allocate advance payment to invoice.
    """
    if not request.user.profile.is_admin:
        messages.error(request, "Permission refusée.")
        return redirect('reporting:dashboard')
    
    advance = get_object_or_404(AdvancePayment, id=advance_id)
    
    if advance.is_fully_allocated:
        messages.error(request, "Cet acompte est déjà entièrement alloué.")
        return redirect('financial:advance_payment_list')
    
    if request.method == 'POST':
        form = AdvanceAllocationForm(
            request.POST,
            client=advance.client,
            advance_payment=advance
        )
        if form.is_valid():
            invoice = form.cleaned_data['invoice']
            amount = form.cleaned_data['amount']
            
            try:
                advance.allocate_to_invoice(invoice, amount)
                messages.success(
                    request,
                    f"{amount} DA alloués à la facture {invoice.reference}."
                )
                return redirect('financial:advance_payment_list')
            except ValueError as e:
                messages.error(request, str(e))
    else:
        form = AdvanceAllocationForm(
            client=advance.client,
            advance_payment=advance
        )
    
    context = {
        'form': form,
        'advance': advance
    }
    
    return render(request, 'financial/advance_allocation_form.html', context)


# ============================================================================
# EXPENSE VIEWS
# ============================================================================

@login_required
def expense_list(request):
    """
    List expenses with advanced filtering.
    """
    if not request.user.profile.is_admin:
        messages.error(request, "Permission refusée.")
        return redirect('reporting:dashboard')
    
    # Filters
    category_id = request.GET.get('category', '')
    allocation = request.GET.get('allocation', '')
    approval_status = request.GET.get('approval', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    vendor_id = request.GET.get('vendor', '')
    is_reimbursable = request.GET.get('reimbursable', '')
    
    expenses = Expense.objects.select_related(
        'category', 'vendor', 'allocated_to_session', 
        'allocated_to_project', 'created_by'
    ).order_by('-date', '-expense_number')
    
    # Apply filters
    if category_id:
        expenses = expenses.filter(category_id=category_id)
    
    if allocation:
        expenses = expenses.filter(allocation_type=allocation)
    
    if approval_status:
        expenses = expenses.filter(approval_status=approval_status)
    
    if date_from:
        expenses = expenses.filter(date__gte=date_from)
    
    if date_to:
        expenses = expenses.filter(date__lte=date_to)
    
    if vendor_id:
        expenses = expenses.filter(vendor_id=vendor_id)
    
    if is_reimbursable == 'true':
        expenses = expenses.filter(is_reimbursable=True, reimbursement_date__isnull=True)
    
    # Summary
    summary = expenses.aggregate(
        total_count=Count('id'),
        total_ht=Sum('amount_ht'),
        total_ttc=Sum('amount_ttc')
    )
    
    # Pagination
    paginator = Paginator(expenses, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Filter options
    categories = ExpenseCategory.objects.filter(is_active=True)
    vendors = Vendor.objects.filter(is_active=True)
    
    context = {
        'page_obj': page_obj,
        'expenses': page_obj.object_list,
        'summary': summary,
        'categories': categories,
        'vendors': vendors,
        'category_filter': category_id,
        'allocation_filter': allocation,
        'approval_filter': approval_status,
        'date_from': date_from,
        'date_to': date_to,
        'vendor_filter': vendor_id,
        'allocation_choices': Expense.ALLOCATION_CHOICES,
        'approval_choices': Expense.APPROVAL_CHOICES,
    }
    
    return render(request, 'financial/expense_list.html', context)


@login_required
def expense_create(request):
    """
    Create new expense.
    """
    if not request.user.profile.is_admin:
        messages.error(request, "Permission refusée.")
        return redirect('reporting:dashboard')
    
    if request.method == 'POST':
        form = ExpenseForm(request.POST, request.FILES)
        if form.is_valid():
            expense = form.save(commit=False)
            expense.created_by = request.user
            
            # Auto-approve if created by admin
            expense.approval_status = Expense.APPROVAL_APPROVED
            expense.approved_by = request.user
            expense.approved_at = timezone.now()
            
            expense.save()
            
            messages.success(
                request,
                f"Dépense {expense.expense_number} enregistrée: {expense.amount_ttc} DA"
            )
            return redirect('financial:expense_list')
        else:
            messages.error(request, "Veuillez corriger les erreurs ci-dessous.")
    else:
        form = ExpenseForm()
    
    context = {
        'form': form,
        'action': 'create'
    }
    
    return render(request, 'financial/expense_form.html', context)


@login_required
def expense_detail(request, expense_id):
    """
    View expense details.
    """
    if not request.user.profile.is_admin:
        messages.error(request, "Permission refusée.")
        return redirect('reporting:dashboard')
    
    expense = get_object_or_404(
        Expense.objects.select_related(
            'category', 'vendor', 'allocated_to_session',
            'allocated_to_project', 'allocated_to_equipment',
            'created_by', 'approved_by', 'reimbursed_to'
        ),
        id=expense_id
    )
    
    context = {
        'expense': expense
    }
    
    return render(request, 'financial/expense_detail.html', context)


@login_required
def expense_edit(request, expense_id):
    """
    Edit existing expense.
    """
    if not request.user.profile.is_admin:
        messages.error(request, "Permission refusée.")
        return redirect('reporting:dashboard')
    
    expense = get_object_or_404(Expense, id=expense_id)
    
    if request.method == 'POST':
        form = ExpenseForm(request.POST, request.FILES, instance=expense)
        if form.is_valid():
            form.save()
            messages.success(request, "Dépense mise à jour avec succès.")
            return redirect('financial:expense_detail', expense_id=expense_id)
        else:
            messages.error(request, "Veuillez corriger les erreurs ci-dessous.")
    else:
        form = ExpenseForm(instance=expense)
    
    context = {
        'form': form,
        'expense': expense,
        'action': 'edit'
    }
    
    return render(request, 'financial/expense_form.html', context)


@login_required
def expense_approve(request, expense_id):
    """
    Approve or reject expense.
    """
    if not request.user.profile.is_admin:
        messages.error(request, "Permission refusée.")
        return redirect('reporting:dashboard')
    
    expense = get_object_or_404(Expense, id=expense_id)
    
    if expense.approval_status != Expense.APPROVAL_PENDING:
        messages.error(request, "Cette dépense a déjà été traitée.")
        return redirect('financial:expense_detail', expense_id=expense_id)
    
    if request.method == 'POST':
        form = ExpenseApprovalForm(request.POST)
        if form.is_valid():
            decision = form.cleaned_data['decision']
            notes = form.cleaned_data['notes']
            
            if decision == 'approve':
                expense.approve(request.user, notes)
                messages.success(request, "Dépense approuvée.")
            else:
                expense.reject(request.user, notes)
                messages.success(request, "Dépense rejetée.")
            
            return redirect('financial:expense_detail', expense_id=expense_id)
    else:
        form = ExpenseApprovalForm()
    
    context = {
        'form': form,
        'expense': expense
    }
    
    return render(request, 'financial/expense_approve_form.html', context)


@login_required
def expense_category_list(request):
    """
    List expense categories.
    """
    if not request.user.profile.is_admin:
        messages.error(request, "Permission refusée.")
        return redirect('reporting:dashboard')
    
    categories = ExpenseCategory.objects.prefetch_related('subcategories').order_by('code')
    
    context = {
        'categories': categories
    }
    
    return render(request, 'financial/expense_category_list.html', context)


@login_required
def expense_category_create(request):
    """
    Create expense category.
    """
    if not request.user.profile.is_admin:
        messages.error(request, "Permission refusée.")
        return redirect('reporting:dashboard')
    
    if request.method == 'POST':
        form = ExpenseCategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Catégorie créée avec succès.")
            return redirect('financial:expense_category_list')
    else:
        form = ExpenseCategoryForm()
    
    context = {
        'form': form
    }
    
    return render(request, 'financial/expense_category_form.html', context)


# ============================================================================
# VENDOR VIEWS
# ============================================================================

@login_required
def vendor_list(request):
    """
    List vendors with purchase totals.
    """
    if not request.user.profile.is_admin:
        messages.error(request, "Permission refusée.")
        return redirect('reporting:dashboard')
    
    vendors = Vendor.objects.annotate(
        expense_count=Count('expenses'),
        total_purchases=Sum('expenses__amount_ttc', filter=Q(
            expenses__approval_status=Expense.APPROVAL_APPROVED
        ))
    ).order_by('name')
    
    context = {
        'vendors': vendors
    }
    
    return render(request, 'financial/vendor_list.html', context)


@login_required
def vendor_create(request):
    """
    Create new vendor.
    """
    if not request.user.profile.is_admin:
        messages.error(request, "Permission refusée.")
        return redirect('reporting:dashboard')
    
    if request.method == 'POST':
        form = VendorForm(request.POST)
        if form.is_valid():
            vendor = form.save()
            messages.success(request, f"Fournisseur '{vendor.name}' créé.")
            return redirect('financial:vendor_list')
    else:
        form = VendorForm()
    
    context = {
        'form': form
    }
    
    return render(request, 'financial/vendor_form.html', context)


@login_required
def vendor_detail(request, vendor_id):
    """
    View vendor details and purchase history.
    """
    if not request.user.profile.is_admin:
        messages.error(request, "Permission refusée.")
        return redirect('reporting:dashboard')
    
    vendor = get_object_or_404(Vendor, id=vendor_id)
    
    expenses = Expense.objects.filter(
        vendor=vendor,
        approval_status=Expense.APPROVAL_APPROVED
    ).order_by('-date')[:20]
    
    total_purchases = expenses.aggregate(total=Sum('amount_ttc'))['total'] or Decimal('0')
    
    context = {
        'vendor': vendor,
        'expenses': expenses,
        'total_purchases': total_purchases
    }
    
    return render(request, 'financial/vendor_detail.html', context)


# ============================================================================
# OUTSTANDING PAYMENTS (AGING REPORT)
# ============================================================================

@login_required
def outstanding_payments(request):
    """
    Aging report for outstanding invoices.
    """
    if not request.user.profile.is_admin:
        messages.error(request, "Permission refusée.")
        return redirect('reporting:dashboard')
    
    today = timezone.now().date()
    
    # Get all outstanding invoices
    outstanding = Invoice.objects.filter(
        status__in=[Invoice.STATUS_UNPAID, Invoice.STATUS_PARTIALLY_PAID],
        is_void=False
    ).select_related('client').order_by('due_date')
    
    # Categorize by aging buckets
    aging_buckets = {
        'current': [],
        '1_30': [],
        '31_60': [],
        '61_90': [],
        'over_90': []
    }
    
    total_by_bucket = {
        'current': Decimal('0'),
        '1_30': Decimal('0'),
        '31_60': Decimal('0'),
        '61_90': Decimal('0'),
        'over_90': Decimal('0')
    }
    
    for invoice in outstanding:
        days_overdue = invoice.days_overdue
        remaining = invoice.amount_remaining
        
        if days_overdue == 0:
            bucket = 'current'
        elif days_overdue <= 30:
            bucket = '1_30'
        elif days_overdue <= 60:
            bucket = '31_60'
        elif days_overdue <= 90:
            bucket = '61_90'
        else:
            bucket = 'over_90'
        
        aging_buckets[bucket].append(invoice)
        total_by_bucket[bucket] += remaining
    
    total_outstanding = sum(total_by_bucket.values())
    
    context = {
        'aging_buckets': aging_buckets,
        'total_by_bucket': total_by_bucket,
        'total_outstanding': total_outstanding,
        'invoice_count': outstanding.count()
    }
    
    return render(request, 'financial/outstanding_payments.html', context)


# ============================================================================
# BUDGET VIEWS
# ============================================================================

@login_required
def budget_list(request):
    """
    List budgets with variance analysis.
    """
    if not request.user.profile.is_admin:
        messages.error(request, "Permission refusée.")
        return redirect('reporting:dashboard')
    
    year = int(request.GET.get('year', timezone.now().year))
    
    budgets = Budget.objects.filter(year=year).select_related('category').order_by('category__code')
    
    # Calculate actuals and variances
    budget_data = []
    for budget in budgets:
        actuals = {
            'q1': budget.get_actual_for_quarter(1),
            'q2': budget.get_actual_for_quarter(2),
            'q3': budget.get_actual_for_quarter(3),
            'q4': budget.get_actual_for_quarter(4),
        }
        
        variances = {
            'q1': budget.q1_budget - actuals['q1'],
            'q2': budget.q2_budget - actuals['q2'],
            'q3': budget.q3_budget - actuals['q3'],
            'q4': budget.q4_budget - actuals['q4'],
        }
        
        budget_data.append({
            'budget': budget,
            'actuals': actuals,
            'variances': variances,
            'total_budget': budget.total_budget,
            'total_actual': sum(actuals.values()),
            'total_variance': sum(variances.values())
        })
    
    context = {
        'budget_data': budget_data,
        'year': year,
        'year_range': range(timezone.now().year - 2, timezone.now().year + 3)
    }
    
    return render(request, 'financial/budget_list.html', context)


@login_required
def budget_create(request):
    """
    Create budget.
    """
    if not request.user.profile.is_admin:
        messages.error(request, "Permission refusée.")
        return redirect('reporting:dashboard')
    
    if request.method == 'POST':
        form = BudgetForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Budget créé avec succès.")
            return redirect('financial:budget_list')
    else:
        form = BudgetForm()
    
    context = {
        'form': form
    }
    
    return render(request, 'financial/budget_form.html', context)


# ============================================================================
# REPORTING VIEWS
# ============================================================================

@login_required
def financial_reports(request):
    """
    Generate various financial reports.
    """
    if not request.user.profile.is_admin:
        messages.error(request, "Permission refusée.")
        return redirect('reporting:dashboard')
    
    form = FinancialReportFilterForm(request.GET or None)
    report_data = None
    report_type = None
    
    if request.GET and form.is_valid():
        report_type = form.cleaned_data['report_type']
        date_from = form.cleaned_data['date_from']
        date_to = form.cleaned_data['date_to']
        group_by = form.cleaned_data['group_by']
        
        if report_type == FinancialReportFilterForm.REPORT_TYPE_REVENUE:
            report_data = generate_revenue_report(date_from, date_to, group_by)
        elif report_type == FinancialReportFilterForm.REPORT_TYPE_EXPENSES:
            report_data = generate_expense_report(date_from, date_to, group_by)
        elif report_type == FinancialReportFilterForm.REPORT_TYPE_CASHFLOW:
            report_data = generate_cashflow_report(date_from, date_to)
        elif report_type == FinancialReportFilterForm.REPORT_TYPE_TVA:
            report_data = generate_tva_report(date_from, date_to)
        
        # Handle export
        export_format = form.cleaned_data.get('export_format')
        if export_format == 'excel':
            return export_report_excel(report_data, report_type)
        elif export_format == 'csv':
            return export_report_csv(report_data, report_type)
    
    context = {
        'form': form,
        'report_data': report_data,
        'report_type': report_type
    }
    
    return render(request, 'financial/financial_reports.html', context)


def generate_revenue_report(date_from, date_to, group_by):
    """Generate revenue report data."""
    invoices = Invoice.objects.filter(
        date__gte=date_from,
        date__lte=date_to,
        is_void=False
    )
    
    # Group data
    data = {
        'total_ht': invoices.aggregate(total=Sum('amount_ht'))['total'] or Decimal('0'),
        'total_tva': invoices.aggregate(total=Sum('amount_tva'))['total'] or Decimal('0'),
        'total_ttc': invoices.aggregate(total=Sum('amount_ttc'))['total'] or Decimal('0'),
        'by_type': {},
        'by_period': []
    }
    
    # By invoice type
    for inv_type, label in Invoice.TYPE_CHOICES:
        type_total = invoices.filter(invoice_type=inv_type).aggregate(
            total=Sum('amount_ttc')
        )['total'] or Decimal('0')
        data['by_type'][label] = type_total
    
    return data


def generate_expense_report(date_from, date_to, group_by):
    """Generate expense report data."""
    expenses = Expense.objects.filter(
        date__gte=date_from,
        date__lte=date_to,
        approval_status=Expense.APPROVAL_APPROVED
    )
    
    data = {
        'total_ht': expenses.aggregate(total=Sum('amount_ht'))['total'] or Decimal('0'),
        'total_tva': expenses.aggregate(total=Sum('tva_amount'))['total'] or Decimal('0'),
        'total_ttc': expenses.aggregate(total=Sum('amount_ttc'))['total'] or Decimal('0'),
        'by_category': [],
        'by_allocation': {}
    }
    
    # By category
    categories = ExpenseCategory.objects.filter(is_active=True)
    for category in categories:
        cat_total = expenses.filter(category=category).aggregate(
            total=Sum('amount_ttc')
        )['total'] or Decimal('0')
        if cat_total > 0:
            data['by_category'].append({
                'category': category,
                'total': cat_total
            })
    
    # By allocation
    for alloc_type, label in Expense.ALLOCATION_CHOICES:
        alloc_total = expenses.filter(allocation_type=alloc_type).aggregate(
            total=Sum('amount_ttc')
        )['total'] or Decimal('0')
        data['by_allocation'][label] = alloc_total
    
    return data


def generate_cashflow_report(date_from, date_to):
    """Generate cash flow report."""
    # Income (payments received)
    payments = Payment.objects.filter(
        date__gte=date_from,
        date__lte=date_to,
        is_reversed=False,
        payment_status=Payment.PAYMENT_STATUS_CLEARED
    )
    
    # Expenses paid
    expenses = Expense.objects.filter(
        payment_date__gte=date_from,
        payment_date__lte=date_to,
        is_paid=True,
        approval_status=Expense.APPROVAL_APPROVED
    )
    
    data = {
        'cash_in': payments.aggregate(total=Sum('amount'))['total'] or Decimal('0'),
        'cash_out': expenses.aggregate(total=Sum('amount_ttc'))['total'] or Decimal('0'),
        'net_cashflow': Decimal('0')
    }
    
    data['net_cashflow'] = data['cash_in'] - data['cash_out']
    
    return data


def generate_tva_report(date_from, date_to):
    """Generate TVA declaration report."""
    # TVA collected (on invoices)
    invoices = Invoice.objects.filter(
        date__gte=date_from,
        date__lte=date_to,
        is_void=False
    )
    
    tva_collected = invoices.aggregate(total=Sum('amount_tva'))['total'] or Decimal('0')
    
    # TVA deductible (on expenses)
    expenses = Expense.objects.filter(
        date__gte=date_from,
        date__lte=date_to,
        approval_status=Expense.APPROVAL_APPROVED
    )
    
    tva_deductible = expenses.aggregate(total=Sum('tva_amount'))['total'] or Decimal('0')
    
    data = {
        'tva_collected': tva_collected,
        'tva_deductible': tva_deductible,
        'tva_net': tva_collected - tva_deductible
    }
    
    return data


def export_report_excel(report_data, report_type):
    """Export report to Excel format."""
    # Placeholder for Excel export
    # In production, use openpyxl or xlsxwriter
    response = HttpResponse(content_type='application/vnd.ms-excel')
    response['Content-Disposition'] = f'attachment; filename="{report_type}_{timezone.now().date()}.xls"'
    return response


def export_report_csv(report_data, report_type):
    """Export report to CSV format."""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{report_type}_{timezone.now().date()}.csv"'
    
    writer = csv.writer(response)
    
    # Write headers and data based on report type
    if report_type == FinancialReportFilterForm.REPORT_TYPE_REVENUE:
        writer.writerow(['Type', 'Montant TTC'])
        for label, amount in report_data['by_type'].items():
            writer.writerow([label, amount])
    
    return response


# ============================================================================
# AJAX ENDPOINTS
# ============================================================================

@login_required
def ajax_get_invoice_stats(request):
    """
    AJAX endpoint for invoice statistics.
    """
    if not request.user.profile.is_admin:
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    today = timezone.now().date()
    
    stats = {
        'total_outstanding': Decimal('0'),
        'overdue_count': 0,
        'overdue_amount': Decimal('0'),
        'this_month_revenue': Decimal('0')
    }
    
    # Outstanding
    outstanding = Invoice.objects.filter(
        status__in=[Invoice.STATUS_UNPAID, Invoice.STATUS_PARTIALLY_PAID],
        is_void=False
    )
    
    for inv in outstanding:
        remaining = inv.amount_remaining
        stats['total_outstanding'] += remaining
        if inv.is_overdue:
            stats['overdue_count'] += 1
            stats['overdue_amount'] += remaining
    
    # This month revenue
    this_month = Invoice.objects.filter(
        date__month=today.month,
        date__year=today.year,
        is_void=False,
        status=Invoice.STATUS_PAID
    ).aggregate(total=Sum('amount_ttc'))['total'] or Decimal('0')
    
    stats['this_month_revenue'] = this_month
    
    # Convert Decimal to float for JSON
    for key in stats:
        if isinstance(stats[key], Decimal):
            stats[key] = float(stats[key])
    
    return JsonResponse(stats)


@login_required
def ajax_get_client_balance(request, client_id):
    """
    AJAX endpoint for client balance.
    """
    if not request.user.profile.is_admin:
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    client = get_object_or_404(Client, id=client_id)
    
    invoices = Invoice.objects.filter(
        client=client,
        is_void=False
    )
    
    total_invoiced = invoices.aggregate(total=Sum('amount_ttc'))['total'] or Decimal('0')
    total_paid = sum(inv.amount_paid for inv in invoices)
    balance = total_invoiced - total_paid
    
    return JsonResponse({
        'total_invoiced': float(total_invoiced),
        'total_paid': float(total_paid),
        'balance': float(balance)
    })
