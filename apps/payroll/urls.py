from django.urls import path

from . import views

app_name = "payroll"

urlpatterns = [
    path("", views.workbench, name="workbench"),
    path("configuration/", views.configuration, name="configuration"),
    path("configuration/employment/new/", views.employment_configuration_create, name="employment_configuration_create"),
    path("configuration/employment/<uuid:configuration_id>/activate/", views.employment_configuration_activate, name="employment_configuration_activate"),
    path("configuration/components/new/", views.component_create, name="component_create"),
    path("configuration/rules/new/", views.rule_create, name="rule_create"),
    path("configuration/rules/<uuid:rule_id>/activate/", views.rule_activate, name="rule_activate"),
    path("periods/new/", views.period_create, name="period_create"),
    path("runs/new/", views.run_create, name="run_create"),
    path("runs/<uuid:run_id>/", views.run_detail, name="run_detail"),
    path("runs/<uuid:run_id>/inputs/new/", views.input_create, name="input_create"),
    path("runs/<uuid:run_id>/adjustments/new/", views.adjustment_create, name="adjustment_create"),
    path("runs/<uuid:run_id>/lock/", views.run_lock, name="run_lock"),
    path("runs/<uuid:run_id>/calculate/", views.run_calculate, name="run_calculate"),
    path("runs/<uuid:run_id>/submit/", views.run_submit, name="run_submit"),
    path("runs/<uuid:run_id>/approve/", views.run_approve, name="run_approve"),
    path("runs/<uuid:run_id>/finalize/", views.run_finalize, name="run_finalize"),
    path("runs/<uuid:run_id>/reverse/", views.run_reverse, name="run_reverse"),
    path("payslips/<uuid:payslip_id>/", views.payslip_detail, name="payslip_detail"),
    path("payslips/<uuid:payslip_id>/export/", views.payslip_export, name="payslip_export"),
    path("history/", views.audit_history, name="audit_history"),
    path("statutory/", views.statutory_workbench, name="statutory_workbench"),
    path("statutory/policies/", views.statutory_policies, name="statutory_policies"),
    path("statutory/calculations/new/", views.statutory_calculation_create, name="statutory_calculation_create"),
    path("statutory/identities/new/", views.statutory_identity_create, name="statutory_identity_create"),
    path("statutory/calculations/<uuid:calculation_id>/review/", views.statutory_calculation_review, name="statutory_calculation_review"),
    path("statutory/calculations/<uuid:calculation_id>/output/", views.statutory_output_generate, name="statutory_output_generate"),
    path("statutory/outputs/<uuid:output_id>/export/", views.statutory_export_record, name="statutory_export_record"),
    path("statutory/evidence/<uuid:evidence_id>/resolve/", views.statutory_export_resolve, name="statutory_export_resolve"),
    path("financial-handoffs/", views.financial_handoff_workbench, name="financial_handoff_workbench"),
    path("financial-handoffs/new/", views.financial_handoff_prepare, name="financial_handoff_prepare"),
    path("financial-handoffs/<uuid:proposal_id>/", views.financial_handoff_detail, name="financial_handoff_detail"),
    path("financial-handoffs/<uuid:proposal_id>/review/", views.financial_handoff_review, name="financial_handoff_review"),
    path("financial-handoffs/<uuid:proposal_id>/reconcile/", views.financial_handoff_reconcile, name="financial_handoff_reconcile"),
]
