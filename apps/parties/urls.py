from django.urls import path

from apps.parties import governance_views, views

app_name = "parties"

urlpatterns = [
    path("governance/", governance_views.index, name="governance"),
    path("governance/<uuid:party_id>/", governance_views.detail, name="governance_detail"),
    path("governance/<uuid:party_id>/actions/<slug:action>/", governance_views.action, name="governance_action"),
    path("", views.party_list, name="list"),
    path("create/", views.party_create, name="create"),
    path("<uuid:party_id>/", views.party_detail, name="detail"),
    path("<uuid:party_id>/archive/", views.party_archive, name="archive"),
    path("<uuid:party_id>/roles/", views.party_role_create, name="role_create"),
    path(
        "<uuid:party_id>/contacts/", views.party_contact_create, name="contact_create"
    ),
]
