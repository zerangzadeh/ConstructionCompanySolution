from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("apps.accounts.urls")),
    path("organizations/", include("apps.organizations.urls")),
    path("audit/", include("apps.audit.urls")),
    path("projects/", include("apps.projects.urls")),
    path("contracts/", include("apps.contracts.urls")),
    path("estimates/", include("apps.estimates.urls")),
    path("expenses/", include("apps.expenses.urls")),
    path("payments/", include("apps.payments.urls")),
    path("documents/", include("apps.documents.urls")),
    path("financials/", include("apps.financials.urls")),
    path("daily-reports/", include("apps.daily_reports.urls")),
]
