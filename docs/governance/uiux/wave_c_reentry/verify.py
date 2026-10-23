"""Final bounded evidence: unchanged baseline, explicit debt, no invented authority."""
import ast
import hashlib
import json
from pathlib import Path
import runpy
import subprocess

OUT = Path(__file__).resolve().parent
R = runpy.run_path(str(OUT/"runtime.py"),run_name="verify_support")
ROOT = R["ROOT"]
from django.apps import apps
from apps.organizations.permission_registry import registered_model_labels
from apps.organizations.models import OrganizationRole, PlatformRoleAssignment, BusinessPermission, PlatformPolicyVersion
from apps.projects.models import BudgetVersion, CostStructureVersion, ProjectBudgetControl
from apps.subledgers.models import MatchTolerancePolicy
from apps.treasury.models import TreasuryAccountMappingVersion
from apps.workforce.models import Person

save = R["save"]
org = R["Organization"].objects.get(slug="demo-construction-01")
before = json.loads((OUT/"RUNTIME_ENTRY.json").read_text(encoding="utf-8"))
# Session primary keys are bearer credentials. Keep only aggregate session hashes/counts.
before["rows"].pop("sessions.Session",None)
save("RUNTIME_ENTRY.json",before)
now = {"models":R["OLD"]["snapshot"](),"rows":R["OLD"]["row_hashes"]()}
now["rows"].pop("sessions.Session",None)
save("RUNTIME_AFTER.json",now)
changed = {label:[key for key,value in rows.items() if now["rows"][label].get(key)!=value] for label,rows in before["rows"].items() if any(now["rows"][label].get(key)!=value for key,value in rows.items())}
added = {label:len(set(rows)-set(before["rows"].get(label,{}))) for label,rows in now["rows"].items() if set(rows)-set(before["rows"].get(label,{}))}
files_before = json.loads((OUT/"FILES_BEFORE.json").read_text(encoding="utf-8"))
file_changes = [name for name,digest in files_before.items() if (ROOT/name).is_file() and hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=digest]
save("INTEGRITY.json",{"existing_row_changes":changed,"added_counts":added,"preexisting_file_changes":file_changes,"head":subprocess.check_output(["git","rev-parse","HEAD"],text=True).strip(),"upstream":subprocess.check_output(["git","rev-parse","@{u}"],text=True).strip(),"index_sha256":hashlib.sha256((ROOT/".git/index").read_bytes()).hexdigest(),"active_temporary_platform_duties":PlatformRoleAssignment.objects.filter(user__username__startswith="uiux.wavec.",revoked_at__isnull=True).count(),"new_permission_codes":BusinessPermission.objects.count()-before["models"]["organizations.BusinessPermission"]["count"],"sessions":"Aggregate only; row keys omitted", "user_last_login":"Excluded by shared row-fingerprint helper"})

missing = sorted({m._meta.label for m in apps.get_app_config("payroll").get_models()}-registered_model_labels())
test_path = "apps/payroll/test_p7_s13_s22_core_payroll.py"
test_name = "test_payroll_registry_is_complete_and_default_roles_are_denied"
def function_dump(source):
    return ast.dump(next(n for n in ast.walk(ast.parse(source)) if isinstance(n,ast.FunctionDef) and n.name==test_name))
original_test = subprocess.check_output(["git","show","HEAD:"+test_path])
unchanged_sources = ["apps/payroll/models.py","apps/organizations/permission_registry.py","apps/organizations/role_defaults.py"]
save("BASELINE_DEBT.json",{"test":test_path+"::CorePayrollTests::"+test_name,"classification":"BASELINE TEST DEBT","missing_registered_model_labels":missing,"failing_test_function_ast_matches_HEAD":function_dump(original_test)==function_dump((ROOT/test_path).read_bytes()),"unchanged_dependencies":{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==files_before[name] for name in unchanged_sources},"attribution":"Failure at model-label set inclusion, before permission/default-role assertions. No changed view/form/template or employment-history code is reached by this assertion.","separate_presentation_assertion":"Updated stale workbench title expectation under PD-WC Payroll terminology remediation; passes in final_tests.xml"})

sources = {"registered_obligation_sources":sorted(__import__("apps.subledgers.services",fromlist=["_SOURCE_RESOLVERS"])._SOURCE_RESOLVERS),"match_tolerance_policies":list(MatchTolerancePolicy.objects.filter(organization=org).values("version_number","quantity_tolerance_bps","unit_price_tolerance_bps","is_approved")),"treasury_account_mappings":TreasuryAccountMappingVersion.objects.filter(organization=org).count(),"treasury_policy_versions":list(PlatformPolicyVersion.objects.filter(policy__code="treasury-self-approval").values("parameters","effective_from","status")),"governing_budgets":ProjectBudgetControl.objects.filter(organization=org,governing_budget__isnull=False).count(),"budget_versions":BudgetVersion.objects.filter(organization=org).count(),"cost_structures":list(CostStructureVersion.objects.filter(organization=org).values("id","status")),"statutory_policy_versions":list(PlatformPolicyVersion.objects.filter(policy__code__in=["payroll-tax-regulatory","employee-insurance-regulatory"]).values("policy__code","status","effective_from"))}
save("SOURCE_GATES.json",sources)
print("Integrity and unchanged-source baseline-debt attribution recorded")
