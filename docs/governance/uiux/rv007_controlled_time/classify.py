"""Classify every one of the 27 original failures by exact cause and final result."""
from support import *
import ast
from collections import Counter
from xml.etree import ElementTree as ET

def cases(path):
    result = {}
    for case in ET.parse(path).iter("testcase"):
        failure = case.find("failure")
        result[case.get("classname") + "." + case.get("name")] = {"result": "FAIL" if failure is not None else "PASS", "message": failure.get("message", "") if failure is not None else ""}
    return result

old = cases(OUT.parent / "rv007_final_closure/affected.xml")
new = cases(OUT / "affected.xml")
probe = read("FROZEN_APPROVER_PROBE.json")
assert probe["result"] == "PermissionDenied" and probe["head_buyer_custom_role"]["result"] == "ALLOWED"
frozen = Path(json.loads((OUT.parent / "wave_c_final_closure/FROZEN_SOURCE.json").read_text())["path"])

def function(path, cls, name):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    nodes = tree.body if cls is None else next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == cls).body
    return ast.dump(next(n for n in nodes if isinstance(n, ast.FunctionDef) and n.name == name), include_attributes=False)

for name in ("_make_actor", "_grant"):
    path = "apps/procurement/test_p5_s10_admissibility.py"
    assert function(ROOT / path, "AdmissibilityFixtureMixin", name) == function(frozen / path, "AdmissibilityFixtureMixin", name)
for name in ("membership_permission_codes", "membership_has_scope", "require_business_permission"):
    path = "apps/organizations/authorization.py"
    assert function(ROOT / path, None, name) == function(frozen / path, None, name)
rows = []
for name, before in old.items():
    if before["result"] != "FAIL":
        continue
    after = new[name]
    row = {"test": name, "original": before, "final": after}
    if "BuyerActionTests" in name:
        assert after["result"] == "PASS"
        row.update(classification="ATTRIBUTABLE_REGRESSION", cause="Accepted shared Procurement fixture marks membership migrated and creates active default-role assignments. Existing buyer override changes only compatibility role_definition, so its custom permissions cease to be effective; close fails before test assertions.", proof="FROZEN_APPROVER_PROBE.json: exact old custom-role plus scope authorizes close under immutable HEAD; SOURCE_ATTRIBUTION.json: shared bootstrap changed but buyer intent and authorizer unchanged; original trace close denial; final same assertions PASS.", fix="Add explicit MembershipRoleAssignment for the existing isolated custom test role. No permission set or assertions changed.", disposition="RESOLVED")
    elif "RFQCloseManifestTests.test_close_permission" in name:
        assert after["result"] == "PASS"
        row.update(classification="ATTRIBUTABLE_REGRESSION", cause="Accepted shared migrated fixture already creates the unrevoked role assignment; scenario unconditionally duplicates it. Shared Organization scope would also mask the intended unrelated-Project denial.", proof="Original UniqueViolation membership_one_unrevoked_role; SOURCE_ATTRIBUTION.json captures earlier shared bootstrap; final exact denial assertion PASS after reusing assignment and removing broad fixture scope.", fix="Reuse explicit assignment and revoke fixture Organization scope before granting the unrelated Project. Authorization denial assertion is preserved and made meaningful.", disposition="RESOLVED")
    else:
        assert after["result"] == "FAIL" and "PermissionDenied" in after["message"]
        row.update(classification="BASELINE_PREEXISTING", cause="Unchanged AdmissibilityFixtureMixin._make_actor creates an active legacy Tenant Manager but no explicit scope. _grant adds the opening-approval permission, which does not supply scope. Shared setUp fails at independent opening approval before scenario assertions.", proof="Frozen/current _make_actor and _grant AST identical; authorization permission/scope/require AST identical. FROZEN_APPROVER_PROBE.json reproduces exact permission-present, scope-absent input under immutable HEAD and returns PermissionDenied in a rolled-back isolated test transaction.", disposition="RETAINED; no unrelated baseline repair or weakening")
    rows.append(row)
counts = Counter(row["classification"] for row in rows)
assert len(rows) == 27
assert counts == {"ATTRIBUTABLE_REGRESSION": 9, "BASELINE_PREEXISTING": 18}
assert sum(case["result"] == "FAIL" for case in new.values()) == 18
save("REGRESSION_ATTRIBUTION.json", {"original_failure_count": 27, "counts": {c: counts[c] for c in ("ATTRIBUTABLE_REGRESSION", "BASELINE_PREEXISTING", "INDETERMINATE")}, "unresolved_attributable_regressions": 0, "all_original_cases_accounted_for": True, "new_failures": [], "final_affected": (OUT / "affected.txt").read_text().strip().splitlines()[-1], "final_focused": (OUT / "focused.txt").read_text().strip().splitlines()[-1], "frozen_full_suite": "Not completed; migration replay superseded by exact immutable-HEAD authority probes; no full frozen-suite PASS claimed", "evidence": ["SOURCE_ATTRIBUTION.json", "FROZEN_APPROVER_PROBE.json", "../rv007_final_closure/affected.xml", "affected.xml", "focused.xml"], "rows": rows})
print(dict(counts), "INDETERMINATE: 0; unresolved attributable: 0")
