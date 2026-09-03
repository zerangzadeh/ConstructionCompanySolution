from django.urls import path

from apps.expenses import views

app_name = "expenses"

urlpatterns = [
    path("", views.expense_list, name="list"),
    path("create/", views.expense_create, name="create"),
    path("<uuid:expense_id>/void/", views.expense_void, name="void"),
]
