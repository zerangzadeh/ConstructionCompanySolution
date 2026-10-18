from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from core.views import global_search, home

admin.site.site_header = "مدیریت سامانه بنیرا"
admin.site.site_title = "مدیریت بنیرا"
admin.site.index_title = "داشبورد مدیریت"

urlpatterns = [
    path("", home, name="home"),
    path("search/", global_search, name="global_search"),
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
    path("commercial/", include("apps.commercial.urls")),
    path("billing/", include("apps.billing.urls")),
    path("estimates/", include("apps.estimates.urls")),
    path("expenses/", include("apps.expenses.urls")),
    path("payments/", include("apps.payments.urls")),
    path("documents/", include("apps.documents.urls")),
    path("financials/", include("apps.financials.urls")),
    path("reporting/", include("apps.reporting.urls")),
    path("daily-reports/", include("apps.daily_reports.urls")),
    path("workforce/", include("apps.workforce.urls")),
    path("timekeeping/", include("apps.timekeeping.urls")),
    path("payroll/", include("apps.payroll.urls")),
    path("procurement/", include("apps.procurement.urls")),
    path("inventory/", include("apps.inventory.urls")),
    path("equipment/", include("apps.equipment.urls")),
    path("fixed-assets/", include("apps.fixed_assets.urls")),
    path("safety/", include("apps.safety.urls")),
    path("quality/", include("apps.quality.urls")),
    path("compliance/", include("apps.compliance.urls")),
    path("partners/", include("apps.partner_qualification.urls")),
    path("support/", include("apps.support.urls")),
    path("knowledge/", include("apps.knowledge.urls")),
    path("workflows/", include("apps.workflows.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
