# ============================================================
# clients/urls.py
# ============================================================

from django.urls import path
from clients import views

app_name = "clients"

urlpatterns = [
    # Clients CRUD
    path("", views.client_list, name="client_list"),
    path("create/", views.client_create, name="client_create"),
    path("<int:pk>/", views.client_detail, name="client_detail"),
    path("<int:pk>/edit/", views.client_edit, name="client_edit"),
    path("<int:pk>/deactivate/", views.client_deactivate, name="client_deactivate"),
    # Contacts (sub-resource of client)
    path("<int:client_pk>/contacts/add/", views.contact_add, name="contact_add"),
    path(
        "<int:client_pk>/contacts/<int:pk>/edit/",
        views.contact_edit,
        name="contact_edit",
    ),
    path(
        "<int:client_pk>/contacts/<int:pk>/delete/",
        views.contact_delete,
        name="contact_delete",
    ),
    # Activity history (read-only aggregate view)
    path("<int:pk>/history/", views.client_history, name="client_history"),
    # AJAX
    path("search/", views.client_search_ajax, name="client_search_ajax"),
]
