from django.urls import path

from apps.partner_qualification import views

app_name = "partner_qualification"
urlpatterns = [
    path("<str:kind>/<uuid:record_id>/", views.record_detail, name="record_detail"),
    path("", views.workbench, name="workbench"),
]
