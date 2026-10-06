from django.urls import path

from apps.equipment import views

app_name = "equipment"

urlpatterns = [
    path("", views.equipment_list, name="list"),
    path("create/", views.equipment_create, name="create"),
    path("<uuid:equipment_id>/", views.equipment_detail, name="detail"),
    path(
        "<uuid:equipment_id>/status/",
        views.equipment_status_change,
        name="status_change",
    ),
    path("<uuid:equipment_id>/archive/", views.equipment_archive, name="archive"),
    path("assignments/", views.assignment_list, name="assignment_list"),
    path("assignments/create/", views.assignment_create, name="assignment_create"),
    path(
        "assignments/<uuid:assignment_id>/status/",
        views.assignment_status_change,
        name="assignment_status_change",
    ),
    path("maintenance/", views.maintenance_list, name="maintenance_list"),
    path("maintenance/create/", views.maintenance_create, name="maintenance_create"),
    path("operations/", views.operations_workbench, name="operations_workbench"),
    path("cost/", views.cost_workbench, name="cost_workbench"),
    path("cost/policies/create/", views.cost_policy_create, name="cost_policy_create"),
    path("cost/rates/create/", views.cost_rate_create, name="cost_rate_create"),
    path(
        "cost/policies/<uuid:policy_id>/<str:action>/",
        views.cost_policy_transition,
        name="cost_policy_transition",
    ),
    path(
        "cost/allocations/create/",
        views.cost_allocation_create,
        name="cost_allocation_create",
    ),
    path(
        "cost/allocations/<uuid:allocation_id>/finalize/",
        views.cost_allocation_finalize,
        name="cost_allocation_finalize",
    ),
    path(
        "cost/allocations/<uuid:allocation_id>/reverse/",
        views.cost_allocation_reverse,
        name="cost_allocation_reverse",
    ),
    path(
        "cost/handoffs/create/", views.cost_handoff_create, name="cost_handoff_create"
    ),
    path(
        "cost/handoffs/<uuid:envelope_id>/review/",
        views.cost_handoff_review,
        name="cost_handoff_review",
    ),
    path(
        "cost/handoffs/<uuid:envelope_id>/reconcile/",
        views.cost_handoff_reconcile,
        name="cost_handoff_reconcile",
    ),
    path(
        "operations/meters/create/",
        views.meter_reading_create,
        name="meter_reading_create",
    ),
    path("operations/usage/create/", views.usage_create, name="usage_create"),
    path("operations/fuel/create/", views.fuel_create, name="fuel_create"),
    path(
        "operations/plans/create/",
        views.maintenance_plan_create,
        name="maintenance_plan_create",
    ),
    path(
        "operations/work-orders/create/",
        views.work_order_create,
        name="work_order_create",
    ),
    path(
        "operations/work-orders/<uuid:work_order_id>/status/",
        views.work_order_transition,
        name="work_order_transition",
    ),
    path(
        "operations/work-orders/<uuid:work_order_id>/spares/create/",
        views.spare_link_create,
        name="spare_link_create",
    ),
    path(
        "operations/qualifications/create/",
        views.operator_qualification_create,
        name="operator_qualification_create",
    ),
    path("operations/downtime/create/", views.downtime_create, name="downtime_create"),
    path(
        "operations/work-orders/<uuid:work_order_id>/evidence/",
        views.work_order_evidence_create,
        name="work_order_evidence_create",
    ),
    path(
        "maintenance/<uuid:record_id>/status/",
        views.maintenance_status_change,
        name="maintenance_status_change",
    ),
]
