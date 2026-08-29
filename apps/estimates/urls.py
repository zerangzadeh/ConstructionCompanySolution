from django.urls import path

from apps.estimates import views

app_name = "estimates"

urlpatterns = [
    path("", views.estimate_list, name="list"),
    path("create/", views.estimate_create, name="create"),
    path("<uuid:estimate_id>/", views.estimate_detail, name="detail"),
    path("<uuid:estimate_id>/approve/", views.estimate_approve, name="approve"),
]
