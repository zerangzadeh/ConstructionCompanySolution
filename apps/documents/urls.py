from django.urls import path

from apps.documents import views

app_name = "documents"

urlpatterns = [
    path("", views.document_list, name="list"),
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
