from django.urls import path

from apps.projects import views

app_name = "projects"

urlpatterns = [
    path("", views.project_list, name="list"),
    path("create/", views.project_create, name="create"),
    path("<uuid:project_id>/", views.project_detail, name="detail"),
    path("<uuid:project_id>/archive/", views.project_archive, name="archive"),
]
