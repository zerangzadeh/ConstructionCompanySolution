from django.urls import path

from apps.projects import views

app_name = "projects"

urlpatterns = [
    path("", views.project_list, name="list"),
    path("create/", views.project_create, name="create"),
    path("<uuid:project_id>/sites/", views.project_site_list, name="site_list"),
    path(
        "<uuid:project_id>/sites/create/",
        views.project_site_create,
        name="site_create",
    ),
    path("<uuid:project_id>/", views.project_detail, name="detail"),
    path("<uuid:project_id>/archive/", views.project_archive, name="archive"),
]
