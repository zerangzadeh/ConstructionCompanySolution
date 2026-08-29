from django.urls import path

from apps.financials import views

app_name = "financials"

urlpatterns = [
    path("dashboard/", views.dashboard, name="dashboard"),
    path("", views.financial_report, name="report"),
]
