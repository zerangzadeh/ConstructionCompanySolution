from django.urls import path

from . import administration_views, views

app_name = "workflows"

urlpatterns = [
    path(
        "administration/", administration_views.definition_list, name="definition_list"
    ),
    path(
        "administration/new/",
        administration_views.definition_create,
        name="definition_create",
    ),
    path(
        "administration/versions/<uuid:version_id>/",
        administration_views.version_detail,
        name="version_detail",
    ),
    path(
        "administration/versions/<uuid:version_id>/edit/",
        administration_views.version_edit,
        name="version_edit",
    ),
    path(
        "administration/versions/<uuid:version_id>/<str:action>/",
        administration_views.version_action,
        name="version_action",
    ),
    path("workbench/", views.workbench, name="workbench"),
    path("my-requests/", views.my_requests, name="my_requests"),
    path("manager/", views.manager_workspace, name="manager_workspace"),
    path(
        "workbench/<uuid:work_item_id>/claim/",
        views.work_item_claim,
        name="work_item_claim",
    ),
    path(
        "workbench/<uuid:work_item_id>/release/",
        views.work_item_release,
        name="work_item_release",
    ),
    path(
        "workbench/<uuid:work_item_id>/action/",
        views.work_item_action,
        name="work_item_action",
    ),
]
