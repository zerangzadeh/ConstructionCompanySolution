"""Development-only entry and fixture discovery for Human-authorized D/E closure."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
sys.path.insert(0, str(OUT.parent / "rv007_controlled_time"))
from support import guard, snapshot, REAL_NOW
from apps.accounts.models import User
from apps.organizations.models import Organization, OrganizationMembership, OrganizationRole
from apps.organizations.authorization import membership_permission_codes, effective_role_assignments, effective_scope_grants, is_platform_admin
from apps.workforce.models import Person, WorkRelationship
from apps.payroll.models import Payslip
from django.db import connection

def save(name, value):
    (OUT / name).write_text(json.dumps(value, default=str, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True, stderr=subprocess.DEVNULL)

guard()
if not (OUT / "ENTRY.json").exists():
    paths = set(git("ls-files").splitlines())
    for parent in ("apps", "core", "config", "templates", "tests", "static", "docs/governance/uiux"):
        paths.update(p.relative_to(ROOT).as_posix() for p in (ROOT / parent).rglob("*") if p.is_file() and "__pycache__" not in p.parts and OUT not in p.parents)
    save("ENTRY.json", {"at": REAL_NOW(), "head": git("rev-parse", "HEAD").strip(), "branch": git("branch", "--show-current").strip(), "upstream": git("rev-parse", "@{u}").strip(), "origin_main": git("rev-parse", "origin/main").strip(), "divergence": git("rev-list", "--left-right", "--count", "HEAD...origin/main").strip(), "status": git("status", "--short"), "diff_name_status": git("diff", "--name-status"), "diff_stat": git("diff", "--stat"), "index_sha256": hashlib.sha256((ROOT / ".git/index").read_bytes()).hexdigest(), "hashes": {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in sorted(paths) if (ROOT / p).is_file()}, "database": {k: connection.settings_dict[k] for k in ("ENGINE", "HOST", "PORT", "NAME")}, "pending_migrations": 0, "authority": "Direct Human request: legitimate RV-016/RV-021 fixture resolution, focused/affected/browser checks, gated RV-025, D/E reconciliation only; no Git writes or CEP/Production", "touch_set": ["Development fixture records through canonical services and existing role/scope mechanisms", "this evidence directory", "current UIUX fixture registry/results/findings/impact map/Wave D/E/completion reports", "minimal demonstrated Development repair only if required by established contract"]})
    save("DATA_BEFORE.json", snapshot())
    for name in ("UIUX_RUNTIME_VALIDATION_RESULTS.yaml", "UIUX_FINDINGS_REGISTER.yaml", "UIUX_ROOT_PATTERN_IMPACT_MAP.yaml", "UIUX_RUNTIME_FIXTURE_REGISTRY.yaml", "UIUX_RUNTIME_VALIDATION_WAVE_D_REPORT.md", "UIUX_RUNTIME_VALIDATION_WAVE_E_REPORT.md", "UIUX_RUNTIME_VALIDATION_COMPLETION_REPORT.md"):
        (OUT / ("entry_" + name)).write_bytes((OUT.parent / name).read_bytes())
org = Organization.objects.get(slug="demo-construction-01")
rows = []
for m in OrganizationMembership.objects.filter(organization=org).select_related("user"):
    codes = sorted(membership_permission_codes(m))
    if m.user.username.startswith("uiux.") or m.user.username in {"admin", "account.demo-construction-01.owner"}:
        rows.append({"alias": m.user.username, "id": m.user_id, "membership": m.pk, "platform_admin": is_platform_admin(m.user), "roles": list(effective_role_assignments(m).values_list("role__code", flat=True)), "permissions": codes, "scope": list(effective_scope_grants(m).values("scope_type", "project_id", "site_id")), "person": list(Person.objects.filter(organization=org, user=m.user).values("id"))})
save("READINESS.json", {"actors": rows, "roles": [{"code": r.code, "permissions": list(r.permissions.values_list("code", flat=True))} for r in OrganizationRole.objects.filter(is_active=True)], "relationships": list(WorkRelationship.objects.filter(organization=org).values("id", "person_id", "person__user__username", "legacy_employee_id", "effective_start", "effective_end")), "payslips": list(Payslip.objects.filter(organization=org).values("id", "run_id", "run__status", "run_employee__employee_id")), "platform_admins": [u.username for u in User.objects.filter(is_active=True) if is_platform_admin(u)]})
print("Entry snapshots saved; live fixture discovery saved without credentials.")
