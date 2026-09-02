from django.urls import path

from apps.payments import views

app_name = "payments"

urlpatterns = [
    path("", views.payment_list, name="list"),
    path("create/", views.payment_create, name="create"),
    path("<uuid:payment_id>/", views.payment_detail, name="detail"),
    path("<uuid:payment_id>/void/", views.payment_void, name="void"),
]
