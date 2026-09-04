from django.urls import path

from apps.projects import views

app_name = "projects"

urlpatterns = [
    path("", views.project_list, name="list"),
    path("create/", views.project_create, name="create"),
    path("<uuid:project_id>/sites/", views.project_site_list, name="site_list"),
    path("<uuid:project_id>/controls/", views.project_controls, name="controls"),
    path("<uuid:project_id>/controls/wbs/", views.wbs_node_create, name="wbs_create"),
    path(
        "<uuid:project_id>/controls/wbs/<uuid:node_id>/archive/",
        views.wbs_node_archive_view,
        name="wbs_archive",
    ),
    path(
        "<uuid:project_id>/controls/activities/",
        views.activity_create,
        name="activity_create",
    ),
    path(
        "<uuid:project_id>/controls/activities/<uuid:activity_id>/transition/",
        views.activity_transition,
        name="activity_transition",
    ),
    path(
        "<uuid:project_id>/controls/activities/<uuid:activity_id>/archive/",
        views.activity_archive_view,
        name="activity_archive",
    ),
    path(
        "<uuid:project_id>/sites/create/",
        views.project_site_create,
        name="site_create",
    ),
    path(
        "<uuid:project_id>/sites/<uuid:site_id>/phases/",
        views.project_phase_list,
        name="phase_list",
    ),
    path(
        "<uuid:project_id>/sites/<uuid:site_id>/phases/create/",
        views.project_phase_create,
        name="phase_create",
    ),
    path(
        "<uuid:project_id>/sites/<uuid:site_id>/phases/<uuid:phase_id>/",
        views.project_phase_detail,
        name="phase_detail",
    ),
    path(
        "<uuid:project_id>/sites/<uuid:site_id>/phases/<uuid:phase_id>/transition/",
        views.project_phase_transition,
        name="phase_transition",
    ),
    path("<uuid:project_id>/", views.project_detail, name="detail"),
    path("<uuid:project_id>/archive/", views.project_archive, name="archive"),
]
