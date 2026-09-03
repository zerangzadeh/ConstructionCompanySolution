from django.urls import path

from apps.documents import views

app_name = "documents"

urlpatterns = [
    path("", views.document_list, name="list"),
    path("upload/", views.document_upload, name="upload"),
    path("<uuid:document_id>/", views.document_detail, name="detail"),
    path("<uuid:document_id>/download/", views.document_download, name="download"),
    path("<uuid:document_id>/archive/", views.document_archive, name="archive"),
]
