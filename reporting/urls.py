# ============================================================
# reporting/urls.py
# ============================================================

from django.urls import path
from reporting import views

app_name = "reporting"

urlpatterns = [
    # Dashboard (root of the application)
    path("", views.dashboard, name="dashboard"),
    # Revenue & financial KPIs
    path("reports/revenue/", views.revenue_summary, name="revenue_summary"),
    path("reports/revenue/by-month/", views.revenue_by_month, name="revenue_by_month"),
    path(
        "reports/revenue/by-client/", views.revenue_by_client, name="revenue_by_client"
    ),
    path(
        "reports/revenue/by-business-line/",
        views.revenue_by_business_line,
        name="revenue_by_business_line",
    ),
    # Outstanding receivables
    path(
        "reports/outstanding/",
        views.outstanding_receivables,
        name="outstanding_receivables",
    ),
    # Margins
    path("reports/margins/sessions/", views.session_margins, name="session_margins"),
    path("reports/margins/projects/", views.project_margins, name="project_margins"),
    # Operational
    path("reports/sessions/", views.sessions_report, name="sessions_report"),
    path("reports/fill-rates/", views.fill_rate_report, name="fill_rate_report"),
    path(
        "reports/trainer-utilization/",
        views.trainer_utilization_report,
        name="trainer_utilization_report",
    ),
    path("reports/top-clients/", views.top_clients_report, name="top_clients_report"),
    # Equipment
    path("reports/equipment/", views.equipment_report, name="equipment_report"),
    # Dashboard chart data (JsonResponse endpoints consumed by the dashboard JS)
    path(
        "api/chart/revenue-trend/",
        views.chart_revenue_trend,
        name="chart_revenue_trend",
    ),
    path(
        "api/chart/business-line-split/",
        views.chart_business_line_split,
        name="chart_business_line_split",
    ),
    path(
        "api/chart/payment-status/",
        views.chart_payment_status,
        name="chart_payment_status",
    ),
    path(
        "api/chart/session-fill-rates/",
        views.chart_session_fill_rates,
        name="chart_session_fill_rates",
    ),
]
