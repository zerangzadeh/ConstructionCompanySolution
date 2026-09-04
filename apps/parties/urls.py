from django.urls import path

from apps.parties import views

app_name = "parties"

urlpatterns = [
    path("", views.party_list, name="list"),
    path("create/", views.party_create, name="create"),
    path("<uuid:party_id>/", views.party_detail, name="detail"),
    path("<uuid:party_id>/archive/", views.party_archive, name="archive"),
    path("<uuid:party_id>/roles/", views.party_role_create, name="role_create"),
    path(
        "<uuid:party_id>/contacts/", views.party_contact_create, name="contact_create"
    ),
]
