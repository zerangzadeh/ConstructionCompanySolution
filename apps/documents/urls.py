from django.urls import path

from apps.documents import contextual_views, evidence_views, views

app_name = "documents"

urlpatterns = [
    path(
        "evidence/choices/<slug:kind>/",
        evidence_views.evidence_choices,
        name="commercial-evidence-choices",
    ),
    path(
        "evidence/<slug:kind>/<uuid:source_id>/choices/",
        evidence_views.evidence_choices,
        name="evidence-choices",
    ),
    path(
        "evidence/<slug:kind>/<uuid:source_id>/register/",
        evidence_views.evidence_register,
        name="evidence-register",
    ),
    path(
        "evidence/<slug:kind>/<uuid:source_id>/<uuid:version_id>/",
        evidence_views.evidence_detail,
        name="evidence-detail",
    ),
    path(
        "context/<slug:target_type>/<uuid:target_id>/upload/",
        contextual_views.contextual_upload,
        name="contextual-upload",
    ),
    path(
        "context/<slug:target_type>/<uuid:target_id>/link/",
        contextual_views.contextual_link,
        name="contextual-link",
    ),
    path(
        "context/<slug:target_type>/<uuid:target_id>/choices/",
        contextual_views.contextual_choices,
        name="contextual-choices",
    ),
    path("", views.document_list, name="list"),
    path("mine/", views.employee_document_list, name="employee-list"),
    path(
        "mine/<uuid:document_id>/",
        views.employee_document_detail,
        name="employee-detail",
    ),
    path(
        "mine/<uuid:document_id>/versions/<uuid:version_id>/download/",
        views.employee_document_download,
        name="employee-version-download",
    ),
    path("upload/", views.document_upload, name="upload"),
    path("<uuid:document_id>/", views.document_detail, name="detail"),
    path("<uuid:document_id>/download/", views.document_download, name="download"),
    path(
        "<uuid:document_id>/photo-preview/",
        views.document_photo_preview,
        name="photo-preview",
    ),
    path(
        "<uuid:document_id>/versions/<uuid:version_id>/download/",
        views.document_version_download,
        name="version-download",
    ),
    path(
        "<uuid:document_id>/versions/add/",
        views.document_version_add,
        name="version-add",
    ),
    path(
        "<uuid:document_id>/links/add/",
        views.document_link_add,
        name="link-add",
    ),
    path("<uuid:document_id>/archive/", views.document_archive, name="archive"),
]
