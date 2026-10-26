from django.urls import path

from apps.compliance import views

app_name = "compliance"

urlpatterns = [
    path(
        "templates/<uuid:template_id>/", views.template_detail, name="template_detail"
    ),
    path("", views.workbench, name="workbench"),
    path("export/", views.export_csv, name="export"),
    path("assurance/", views.assurance, name="assurance"),
    path("create/<str:kind>/", views.create_record, name="create"),
    path(
        "templates/<uuid:template_id>/publish/",
        views.template_publish,
        name="template_publish",
    ),
    path("<str:kind>/<uuid:record_id>/", views.record_detail, name="detail"),
    path(
        "<str:kind>/<uuid:record_id>/transition/",
        views.record_transition,
        name="transition",
    ),
    path("<str:kind>/<uuid:record_id>/evidence/", views.evidence_link, name="evidence"),
]
