from django.urls import path

from apps.contracts import views

app_name = "contracts"

urlpatterns = [
    path("", views.contract_list, name="list"),
    path("create/", views.contract_create, name="create"),
    path("<uuid:contract_id>/", views.contract_detail, name="detail"),
]
