from django.urls import path

from apps.commercial import views

app_name = "commercial"

urlpatterns = [
    path("", views.tender_list, name="tender_list"),
    path("create/", views.tender_create, name="tender_create"),
    path("<uuid:tender_id>/", views.tender_detail, name="tender_detail"),
    path("<uuid:tender_id>/revise/", views.tender_revise, name="tender_revise"),
    path(
        "<uuid:tender_id>/transition/",
        views.tender_transition,
        name="tender_transition",
    ),
    path("<uuid:tender_id>/evidence/", views.tender_evidence, name="tender_evidence"),
]
