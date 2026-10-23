"""Existing focused convergence tests only; never modifies application sources."""
import json
import os
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[4]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
os.environ["GIT_OPTIONAL_LOCKS"] = "0"

import django

django.setup()
from django.conf import settings
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

assert settings.SETTINGS_MODULE == "config.settings.development" and settings.DEBUG
assert connection.vendor == "postgresql"
assert connection.settings_dict["NAME"] == "construction_erp"
assert connection.settings_dict["HOST"] in {"localhost", "127.0.0.1", "::1"}
assert not MigrationExecutor(connection).migration_plan(MigrationExecutor(connection).loader.graph.leaf_nodes())
with connection.cursor() as cursor:
    cursor.execute("SELECT datname FROM pg_database WHERE datname = %s", ["test_construction_erp"])
    assert cursor.fetchone(), "Do not create an unprepared test environment implicitly"
connection.close()

selection = {
    "core/test_home.py::HomeTests": ["test_normal_home_has_context_and_only_links_not_business_facts", "test_scope_removes_business_link_even_with_permission", "test_error_state_is_safe"],
    "apps/organizations/test_cep016_context.py::CEP016ContextTests": ["test_valid_project_and_site_context_persist_and_render_in_rtl_shell", "test_context_route_rejects_unauthorized_and_cross_tenant_ids_without_leak", "test_bound_stale_project_and_phase_are_rejected_server_side", "test_cascade_endpoint_returns_only_authorized_parent_choices"],
    "core/test_cep003_localization_accessibility.py::Cep003LocalizationAccessibilityTests": ["test_persian_jalali_date_input_preserves_gregorian_storage_semantics", "test_shared_field_component_associates_help_and_errors_without_dropping_existing_ids"],
    "core/test_cep017_navigation.py::Cep017NavigationTemplateTests": ["test_canonical_navigation_register_is_complete_and_persian_first", "test_shared_breadcrumb_and_mobile_close_contract_are_present"],
    "apps/workflows/test_cep018_workspaces.py::Cep018WorkspaceTests": ["test_my_requests_is_own_identity_scoped_and_source_owned", "test_manager_workspace_requires_explicit_team_lead_and_filters_team", "test_missing_authorization_scope_fails_closed"],
    "apps/workforce/test_cep026_ess_privacy.py::ESSOwnDataPrivacyTests": ["test_username_email_and_employee_number_similarity_never_infer_identity", "test_other_person_and_cross_tenant_relationships_are_denied", "test_direct_url_masks_sensitive_field_and_discloses_no_other_object"],
    "apps/workflows/test_cep046_administration.py::AdministrationTests": ["test_complete_lifecycle_uses_existing_services_and_preserves_old_graph", "test_permissions_are_independent_and_direct_actions_fail_closed", "test_cross_tenant_objects_and_selected_context_do_not_expand_authority"],
    "apps/workforce/test_cep053.py::ESSDashboardTests": ["test_dashboard_localizes_source_status_and_retains_own_links", "test_independent_profile_survives_source_error", "test_current_person_relationship_bridge_filters_legacy_source_rows"],
    "apps/payroll/test_cep054.py::ESSPayrollTests": ["test_finalized_own_artifact_and_export_preserve_source", "test_own_identity_and_source_state_fail_closed", "test_missing_configuration_or_route_never_creates_orphan", "test_assigned_response_atomicity_privacy_and_no_financial_mutation"],
    "apps/workforce/test_cep055.py::PersonalChangeTests": ["test_all_five_governed_enrollment_rows_apply_only_own_source_after_acceptance", "test_permission_tenant_assignment_and_sensitive_fields_fail_closed", "test_own_status_adapters_preserve_source_scope_and_hide_internal_metadata"],
    "apps/workforce/test_cep056.py::CertificateTests": ["test_missing_renderer_or_activation_cannot_be_enabled_or_generate", "test_evidence_is_own_source_read_only_without_broad_backoffice_grant", "test_generic_dms_and_employee_paths_cannot_bypass_certificate_case_scope"],
    "apps/workforce/test_cep063.py::ESSTimekeepingTests": ["test_empty_index_policy_absence_and_rtl_jalali_ui", "test_own_leave_reservation_and_source_submit_without_balance_manager", "test_attendance_original_and_correction_request_remain_source_owned", "test_timesheet_create_add_submit_tracks_authoritative_source"],
    "apps/workforce/test_cep068.py::ESSOvertimeTests": ["test_source_create_submit_status_and_identity_audit_remain_atomic", "test_own_source_filter_and_missing_or_foreign_urls_have_same_denial"],
    "apps/workforce/test_cep068_mission.py::ESSMissionTests": ["test_persian_jalali_http_empty_form_error_draft_and_submit", "test_approved_request_does_not_activate_unapproved_monetary_policy", "test_own_routing_link_is_projection_only_and_hides_financial_reviewer_data"],
}
nodes = [prefix + "::" + name for prefix, names in selection.items() for name in names]
command = [sys.executable, "-m", "pytest", *nodes, "-q", "--reuse-db", "--disable-warnings", "--tb=no", "-p", "no:cacheprovider", "--junitxml=" + str(OUT / "GATE07_FOCUSED.xml")]
started = datetime.now(timezone(timedelta(hours=3, minutes=30))).isoformat()
print("Development guard PASS; running " + str(len(nodes)) + " existing focused convergence tests.", flush=True)
result = subprocess.run(command, cwd=ROOT, text=True, encoding="utf-8", errors="replace", capture_output=True)
(OUT / "GATE07_FOCUSED.txt").write_text(result.stdout + result.stderr, encoding="utf-8")
tree = ET.parse(OUT / "GATE07_FOCUSED.xml")
cases = []
for case in tree.getroot().iter("testcase"):
    issue = case.find("failure")
    if issue is None:
        issue = case.find("error")
    if issue is not None:
        issue.set("message", issue.get("message", "").split("in the following response")[0][:1500])
        issue.text = (issue.text or "").split("in the following response")[0][:4000]
    cases.append({"test": case.get("classname", "") + "." + case.get("name", ""), "result": "FAIL" if issue is not None else "SKIP" if case.find("skipped") is not None else "PASS", "diagnostic": issue.get("message") if issue is not None else None})
tree.write(OUT / "GATE07_FOCUSED.xml", encoding="utf-8", xml_declaration=True)
summary = {"started_at": started, "ended_at": datetime.now(timezone(timedelta(hours=3, minutes=30))).isoformat(), "command": command, "guard": "Configured Development/DEBUG/loopback PostgreSQL and fully migrated development schema; normal existing test_construction_erp reused; no business DB fixture mutation", "requested_test_nodes": len(nodes), "exit_code": result.returncode, "cases": cases, "counts": {s: sum(c["result"] == s for c in cases) for s in ("PASS", "FAIL", "SKIP")}, "scope": "GATE07 convergence evidence only; no browser runtime or AC PASS implied", "failure_html_csrf_redacted": True}
(OUT / "GATE07_FOCUSED.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(summary["counts"]), flush=True)
sys.exit(result.returncode)
