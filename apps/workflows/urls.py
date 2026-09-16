from django.urls import path

from . import views

app_name = "workflows"

urlpatterns = [
    path("workbench/", views.workbench, name="workbench"),
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
