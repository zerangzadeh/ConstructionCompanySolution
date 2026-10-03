from django.urls import path

from apps.contracts import views

app_name = "contracts"

urlpatterns = [
    path("", views.contract_list, name="list"),
    path("create/", views.contract_create, name="create"),
    path("contractual-records/", views.contractual_record_list, name="contractual_list"),
    path("<uuid:contract_id>/commercial-review/", views.commercial_review, name="commercial_review"),
    path("contractual-records/create/", views.contractual_record_create, name="contractual_create"),
    path("contractual-records/<uuid:record_id>/", views.contractual_record_detail, name="contractual_detail"),
    path("contractual-records/<uuid:record_id>/submit/", views.contractual_record_submit, name="contractual_submit"),
    path("contractual-records/<uuid:record_id>/decide/", views.contractual_record_decide, name="contractual_decide"),
    path("contractual-records/<uuid:record_id>/revision/", views.contractual_record_revision, name="contractual_revision"),
    path("contractual-records/<uuid:record_id>/withdraw/", views.contractual_record_withdraw, name="contractual_withdraw"),
    path("<uuid:contract_id>/", views.contract_detail, name="detail"),
]
