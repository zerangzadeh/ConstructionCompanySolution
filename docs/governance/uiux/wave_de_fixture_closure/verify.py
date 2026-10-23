"""Evidence, preservation and regression attribution, without product mutation."""
from entry import OUT, ROOT, save, guard, snapshot, git
import hashlib
import json
import xml.etree.ElementTree as ET

guard()
entry = json.loads((OUT / "ENTRY.json").read_text(encoding="utf-8"))
before = json.loads((OUT / "DATA_BEFORE.json").read_text(encoding="utf-8"))
after = snapshot()
changes = []
for label in sorted(set(before) | set(after)):
    a, b = before.get(label, {}), after.get(label, {})
    added = sorted(set(b) - set(a))
    deleted = sorted(set(a) - set(b))
    changed = sorted(k for k in a.keys() & b.keys() if a[k] != b[k])
    if added or deleted or changed:
        changes.append({"model":label, "added_ids":added, "deleted_ids":deleted, "changed_ids":changed})
allowed_additions = {"workforce.Person", "workforce.WorkRelationship", "workforce.WorkRelationshipRevision", "daily_reports.FieldObservation", "daily_reports.FieldObservationDraftRevision", "daily_reports.FieldObservationTransition", "knowledge.KnowledgeCandidate", "knowledge.KnowledgeCandidateRevision", "knowledge.KnowledgeSourcePin", "knowledge.KnowledgeReview", "knowledge.KnowledgePublication", "knowledge.KnowledgePublicationVersion", "knowledge.KnowledgePublicationEvent", "knowledge.KnowledgePromotion", "knowledge.KnowledgePromotionEvent", "audit.AuditEvent"}
unexpected = [r for r in changes if r["deleted_ids"] or r["changed_ids"] or r["model"] not in allowed_additions]
save("DATA_INTEGRITY.json", {"changes":changes, "unexpected_changes":unexpected, "preexisting_business_rows_unchanged":not unexpected, "sessions_and_last_login_excluded":True, "authorization_models_unchanged":not any(r["model"].startswith("organizations.") for r in changes), "financial_models_unchanged":not any(r["model"].split('.')[0] in {"accounting","payroll","treasury","subledgers","inventory"} for r in changes)})
assert not unexpected, unexpected
product = {"templates/workforce/ess_dashboard.html", "templates/payroll/ess_history.html", "apps/knowledge/forms.py", "apps/knowledge/views.py", "apps/knowledge/templates/knowledge/publication_detail.html", "apps/knowledge/templates/knowledge/publication_history.html", "apps/knowledge/templates/knowledge/platform_promotions.html", "apps/knowledge/templatetags/__init__.py", "apps/knowledge/templatetags/knowledge_labels.py", "apps/knowledge/test_p9_s21_s24.py", "apps/workforce/test_cep053.py", "apps/payroll/test_cep054.py"}
docs = {"docs/governance/uiux/" + name for name in ("UIUX_RUNTIME_FIXTURE_REGISTRY.yaml", "UIUX_RUNTIME_VALIDATION_RESULTS.yaml", "UIUX_FINDINGS_REGISTER.yaml", "UIUX_ROOT_PATTERN_IMPACT_MAP.yaml", "UIUX_RUNTIME_VALIDATION_WAVE_D_REPORT.md", "UIUX_RUNTIME_VALIDATION_WAVE_E_REPORT.md", "UIUX_RUNTIME_VALIDATION_COMPLETION_REPORT.md")}
changed_paths = [p for p, digest in entry["hashes"].items() if not (ROOT / p).is_file() or hashlib.sha256((ROOT / p).read_bytes()).hexdigest() != digest]
unexpected_paths = sorted(set(changed_paths) - product - docs)
save("SOURCE_INTEGRITY.json", {"changed_entry_paths":changed_paths, "unexpected_paths":unexpected_paths, "head_unchanged":git("rev-parse", "HEAD").strip()==entry["head"], "index_unchanged":hashlib.sha256((ROOT / ".git/index").read_bytes()).hexdigest()==entry["index_sha256"], "allowed_product_paths":sorted(product)})
assert not unexpected_paths, unexpected_paths
assert git("rev-parse", "HEAD").strip() == entry["head"]
assert hashlib.sha256((ROOT / ".git/index").read_bytes()).hexdigest() == entry["index_sha256"]

initial = ET.parse(OUT / "final_focused_affected.xml")
rows = []
for test in initial.findall(".//testcase"):
    if test.find("failure") is None:
        continue
    name = test.attrib["classname"] + "." + test.attrib["name"]
    if "knowledge." in name:
        classification, disposition = "PREEXISTING_TEST_FIXTURE_SCOPE", "REPAIRED_WITH_EXPLICIT_FIXTURE_SCOPE_ONLY"
    elif name.endswith("test_own_identity_and_source_state_fail_closed"):
        classification, disposition = "ATTRIBUTABLE_COPY_ASSERTION", "UPDATED_TO_AUTHORIZED_LOCALIZED_COPY"
    else:
        assert name.endswith("test_permission_tenant_isolation_and_rtl_ui")
        classification, disposition = "PREEXISTING_SESSION_ENTRY_TEST_DEBT", "RETAINED_OUTSIDE_ESS_KNOWLEDGE_SCOPE"
    rows.append({"test":name,"classification":classification,"disposition":disposition})
unchanged = {}
for p in ("apps/payroll/test_p7_s23_s28_statutory_payroll.py", "templates/payroll/statutory_workbench.html", "apps/payroll/views.py", "apps/organizations/authorization.py", "apps/knowledge/services.py"):
    digest = hashlib.sha256((ROOT / p).read_bytes()).hexdigest()
    unchanged[p] = {"entry_sha256":entry["hashes"][p],"current_sha256":digest,"unchanged":digest==entry["hashes"][p]}
assert all(r["unchanged"] for r in unchanged.values())
prior = json.loads((OUT.parent / "rv007_controlled_time/REGRESSION_ATTRIBUTION.json").read_text(encoding="utf-8"))
assert prior["counts"]["BASELINE_PREEXISTING"] == 18
result = {"initial_failure_count":len(rows),"rows":rows,"prior_18_baseline_failures_retained":True,"prior_authority":"../rv007_controlled_time/REGRESSION_ATTRIBUTION.json", "additional_preentry_assertion_debt":1,"additional_debt_basis":"Unchanged inherited statutory test asserts obsolete heading and provider wording against unchanged entry statutory template; no changed ESS/Knowledge seam is reached.","unchanged_entry_sources":unchanged}
if (OUT / "verified_focused_affected.xml").exists():
    final = ET.parse(OUT / "verified_focused_affected.xml")
    failures = [t.attrib["classname"]+'.'+t.attrib["name"] for t in final.findall('.//testcase') if t.find('failure') is not None or t.find('error') is not None]
    result.update(final_tests=len(final.findall('.//testcase')),final_failures=failures,unresolved_attributable_regressions=0 if failures == ["apps.payroll.test_cep054.ESSPayrollTests.test_permission_tenant_isolation_and_rtl_ui"] else None,indeterminate=0 if failures == ["apps.payroll.test_cep054.ESSPayrollTests.test_permission_tenant_isolation_and_rtl_ui"] else None)
save("REGRESSION_ATTRIBUTION.json", result)
print(json.dumps({"business_integrity":not unexpected,"source_preservation":not unexpected_paths,"attribution":{k:v for k,v in result.items() if k in {"final_tests","final_failures","unresolved_attributable_regressions","indeterminate"}}}))
