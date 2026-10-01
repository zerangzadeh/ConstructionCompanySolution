from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "مدیریت سامانه سازه‌یار"
admin.site.site_title = "مدیریت سازه‌یار"
admin.site.index_title = "داشبورد مدیریت"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("apps.accounts.urls")),
    path("organizations/", include("apps.organizations.urls")),
    path("audit/", include("apps.audit.urls")),
    path("accounting/", include("apps.accounting.urls")),
    path("treasury/", include("apps.treasury.urls")),
    path("subledgers/", include("apps.subledgers.urls")),
    path("parties/", include("apps.parties.urls")),
    path("materials/", include("apps.materials.urls")),
    path("projects/", include("apps.projects.urls")),
    path("contracts/", include("apps.contracts.urls")),
    path("billing/", include("apps.billing.urls")),
    path("estimates/", include("apps.estimates.urls")),
    path("expenses/", include("apps.expenses.urls")),
    path("payments/", include("apps.payments.urls")),
    path("documents/", include("apps.documents.urls")),
    path("financials/", include("apps.financials.urls")),
    path("daily-reports/", include("apps.daily_reports.urls")),
    path("workforce/", include("apps.workforce.urls")),
    path("procurement/", include("apps.procurement.urls")),
    path("inventory/", include("apps.inventory.urls")),
    path("equipment/", include("apps.equipment.urls")),
    path("safety/", include("apps.safety.urls")),
    path("quality/", include("apps.quality.urls")),
    path("workflows/", include("apps.workflows.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
