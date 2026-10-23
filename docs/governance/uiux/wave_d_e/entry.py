"""Read-only Development entry evidence for the authorized Wave D/E audit."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
sys.path.insert(0, str(OUT.parent / "rv007_controlled_time"))
from support import guard, snapshot, REAL_NOW
from django.apps import apps
from django.db import connection
from apps.accounts.models import User
from apps.organizations.models import Organization, OrganizationMembership
from apps.organizations.authorization import (
    effective_role_assignments, membership_permission_codes, is_platform_admin,
)
from apps.workforce.ess_services import has_ess_subject


def save(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True, stderr=subprocess.DEVNULL)


guard()
assert not (OUT / "ENTRY.json").exists(), "Preserve prior entry evidence"
paths = set(git("ls-files").splitlines())
for parent in ("apps", "core", "config", "templates", "tests", "static", "docs/governance/uiux"):
    paths.update(str(p.relative_to(ROOT)).replace("\\", "/") for p in (ROOT / parent).rglob("*") if p.is_file() and "__pycache__" not in p.parts and OUT not in p.parents)
hashes = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in sorted(paths) if (ROOT / p).is_file()}
save("ENTRY.json", {
    "at": REAL_NOW(), "branch": git("branch", "--show-current").strip(),
    "head": git("rev-parse", "HEAD").strip(), "upstream": git("rev-parse", "@{u}").strip(),
    "origin_main": git("rev-parse", "origin/main").strip(), "status": git("status", "--short"),
    "diff_name_status": git("diff", "--name-status"), "diff_stat": git("diff", "--stat"),
    "hashes": hashes, "index_sha256": hashlib.sha256((ROOT / ".git/index").read_bytes()).hexdigest(),
    "authority": "Human attached Wave D then E serial Development runtime-validation request, 2026-10-23; bounded demonstrated UI remediation only; no grants/identity provisioning/business mutation/CEP/Git writes",
    "actual_execution_touch_set_at_entry": ["docs/governance/uiux/wave_d_e/", "UIUX_RUNTIME_VALIDATION_RESULTS.yaml", "UIUX_FINDINGS_REGISTER.yaml", "Wave D/E reports; product additions only if directly demonstrated and bounded"],
    "database": {k: connection.settings_dict[k] for k in ("ENGINE", "HOST", "PORT", "NAME")},
    "pending_migrations": 0,
})
save("DATA_BEFORE.json", snapshot())
for filename in ("UIUX_RUNTIME_VALIDATION_RESULTS.yaml", "UIUX_FINDINGS_REGISTER.yaml"):
    (OUT / ("entry_" + filename)).write_bytes((OUT.parent / filename).read_bytes())
org = Organization.objects.get(slug="demo-construction-01")
fixture = json.loads((OUT.parent / "UIUX_RUNTIME_FIXTURE_REGISTRY.yaml").read_text(encoding="utf-8-sig"))
aliases = {p["identity"] for p in fixture["personas"] if p.get("identity")}
aliases.update(User.objects.filter(username__startswith="uiux.").values_list("username", flat=True))
rows = []
for user in User.objects.filter(username__in=aliases).order_by("username"):
    m = OrganizationMembership.objects.filter(user=user, organization=org).first()
    rows.append({"alias": user.username, "active": user.is_active,
        "platform_admin": is_platform_admin(user), "membership": str(m.pk) if m else None,
        "membership_status": m.status if m else None,
        "roles": list(effective_role_assignments(m).values_list("role__code", flat=True)) if m else [],
        "permissions": sorted(membership_permission_codes(m)) if m else [],
        "scope": list(m.scope_assignments.values()) if m and hasattr(m,"scope_assignments") else [],
        "ess_subject": has_ess_subject(user=user, organization=org) if m else False})
objects = {}
for label in ("safety.SafetyIncident", "quality.QualityIssue", "knowledge.KnowledgePublicationVersion", "knowledge.KnowledgePublication", "workflows.WorkflowVersion", "workflows.WorkflowDefinition", "workforce.Person"):
    model = apps.get_model(label)
    fields = {f.name for f in model._meta.concrete_fields}
    include = [f.attname for f in model._meta.concrete_fields if f.name in {"id","organization","project","site","status","version","publication","definition","user"}]
    qs = model.objects.all()
    if "organization" in fields: qs = qs.filter(organization=org)
    objects[label] = list(qs.values(*include))
save("READINESS.json", {"organization": str(org.pk), "status":org.status, "personas":rows, "objects":objects})
attribution = json.loads((OUT.parent / "rv007_controlled_time/REGRESSION_ATTRIBUTION.json").read_text(encoding="utf-8"))
debt = []
for row in attribution["rows"]:
    if row["classification"] != "BASELINE_PREEXISTING": continue
    debt.append({"test":row["test"], "classification":"INTERSECTS_WAVE_SCOPE", "cause":row["cause"],
        "impact":"Procurement protected-opening/admissibility/comparison fixture debt intersects Wave E buyer surface; does not exercise ESS/Safety/Quality/Knowledge/Workflow Wave D. Retained exact prior attribution; positive retained RV-007 browser evidence and current actor/scope must be checked separately."})
save("BASELINE_DEBT_REVIEW.json", {"count":len(debt), "rows":debt, "reclassified":False,
    "wave_d":"NON_BLOCKING_BASELINE_DEBT", "wave_e":"INTERSECTS_WAVE_SCOPE; not an automatic blocker", "indeterminate":0})
print(json.dumps({"personas":[{k:v for k,v in r.items() if k not in {"permissions","scope"}} for r in rows],"objects":objects,"baseline_retained":len(debt)},ensure_ascii=True,indent=2))
