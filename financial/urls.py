# ============================================================
# financial/urls.py
# ============================================================

from django.urls import path
from financial import views

app_name = "financial"

urlpatterns = [
    # --- Invoices ---
    path("invoices/", views.invoice_list, name="invoice_list"),
    path("invoices/create/", views.invoice_create, name="invoice_create"),
    path(
        "invoices/create/formation/<int:session_pk>/",
        views.invoice_create_from_session,
        name="invoice_create_from_session",
    ),
    path(
        "invoices/create/etude/<int:project_pk>/",
        views.invoice_create_from_project,
        name="invoice_create_from_project",
    ),
    path("invoices/<int:pk>/", views.invoice_detail, name="invoice_detail"),
    path("invoices/<int:pk>/edit/", views.invoice_edit, name="invoice_edit"),
    path("invoices/<int:pk>/void/", views.invoice_void, name="invoice_void"),
    path(
        "invoices/<int:pk>/print/", views.invoice_print, name="invoice_print"
    ),  # printable HTML
    # --- Invoice line items (AJAX-driven inline editing) ---
    path("invoices/<int:invoice_pk>/items/add/", views.item_add, name="item_add"),
    path(
        "invoices/<int:invoice_pk>/items/<int:pk>/edit/",
        views.item_edit,
        name="item_edit",
    ),
    path(
        "invoices/<int:invoice_pk>/items/<int:pk>/delete/",
        views.item_delete,
        name="item_delete",
    ),
    # --- Payments ---
    path(
        "invoices/<int:invoice_pk>/payments/add/",
        views.payment_add,
        name="payment_add",
    ),
    path(
        "invoices/<int:invoice_pk>/payments/<int:pk>/edit/",
        views.payment_add,  # ← same view, pk makes it edit mode
        name="payment_edit",
    ),
    path(
        "invoices/<int:invoice_pk>/payments/<int:pk>/delete/",
        views.payment_delete,
        name="payment_delete",
    ),
    path(
        "invoices/<int:invoice_pk>/payments/<int:pk>/confirm/",
        views.payment_confirm,
        name="payment_confirm",
    ),
    path(
        "invoices/<int:invoice_pk>/payments/<int:pk>/reverse/",
        views.payment_reverse,
        name="payment_reverse",
    ),
    # --- Credit notes ---
    path("credit-notes/", views.credit_note_list, name="credit_note_list"),
    path(
        "invoices/<int:invoice_pk>/credit-notes/create/",
        views.credit_note_create,
        name="credit_note_create",
    ),
    path("credit-notes/<int:pk>/", views.credit_note_detail, name="credit_note_detail"),
    path(
        "credit-notes/<int:pk>/print/",
        views.credit_note_print,
        name="credit_note_print",
    ),
    # --- Expenses ---
    path("expenses/", views.expense_list, name="expense_list"),
    path("expenses/create/", views.expense_create, name="expense_create"),
    path("expenses/<int:pk>/edit/", views.expense_edit, name="expense_edit"),
    path("expenses/<int:pk>/delete/", views.expense_delete, name="expense_delete"),
    path("expenses/<int:pk>/approve/", views.expense_approve, name="expense_approve"),
    path("expenses/<int:pk>/reject/", views.expense_reject, name="expense_reject"),
    # Expense categories
    path(
        "expenses/categories/",
        views.expense_category_list,
        name="expense_category_list",
    ),
    path(
        "expenses/categories/create/",
        views.expense_category_create,
        name="expense_category_create",
    ),
    path(
        "expenses/categories/<int:pk>/edit/",
        views.expense_category_edit,
        name="expense_category_edit",
    ),
    # --- Financial periods ---
    path("periods/", views.period_list, name="period_list"),
    path("periods/create/", views.period_create, name="period_create"),
    path("periods/<int:pk>/", views.period_detail, name="period_detail"),
    path("periods/<int:pk>/edit/", views.period_edit, name="period_edit"),
    path("periods/<int:pk>/close/", views.period_close, name="period_close"),
    # --- Analytics & reporting ---
    path("analytics/", views.financial_analytics, name="analytics"),
    path("analytics/revenue/", views.revenue_report, name="revenue_report"),
    path("analytics/outstanding/", views.outstanding_report, name="outstanding_report"),
    path("analytics/expenses/", views.expense_report, name="expense_report"),
    path("analytics/margins/", views.margin_report, name="margin_report"),
    path(
        "analytics/revenue/chart-data/",
        views.revenue_chart_data,
        name="revenue_chart_data",
    ),  # JsonResponse
]
