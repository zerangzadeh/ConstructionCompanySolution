"""Bounded Development closure evidence; no credentials are serialized."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
sys.path.insert(0, str(OUT.parent / "rv007_controlled_time"))
from support import guard, snapshot, REAL_NOW


def save(name, data):
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True, stderr=subprocess.DEVNULL)


guard()
if __name__ == "__main__":
    assert not (OUT / "ENTRY.json").exists()
    files = [p for parent in ("apps", "core", "config", "templates", "tests", "static", "docs/governance/uiux") for p in (ROOT / parent).rglob("*") if p.is_file() and "__pycache__" not in p.parts and OUT not in p.parents]
    files += [ROOT / p for p in ("CEP_EXECUTION_REGISTRY.yaml", "ROADMAP.md")]
    save("ENTRY.json", {"recorded_at": REAL_NOW(), "branch": git("branch", "--show-current").strip(), "head": git("rev-parse", "HEAD").strip(), "upstream": git("rev-parse", "@{u}").strip(), "origin_main": git("rev-parse", "origin/main").strip(), "status": git("status", "--short"), "diff_name_status": git("diff", "--name-status"), "diff_stat": git("diff", "--stat"), "index_sha256": sha(ROOT / ".git/index"), "hashes": {p.relative_to(ROOT).as_posix(): sha(p) for p in files}, "authority": "Direct Human: F-110 date accessible names, F-134 static Tenant label, canonical fresh external invitation; focused/affected/browser validation and Wave E/final reconciliation only; STOP; no Git writes/CEP/Production/sign-off", "scope": ["shared date-range labels and corresponding calendar names", "role catalogue static filter label", "new canonical test portal invitation/grant", "targeted tests and UIUX evidence/reconciliation"]})
    save("DATA_BEFORE.json", snapshot())
    from apps.procurement.models import SupplierPortalGrant
    g = SupplierPortalGrant.objects.select_related("portal_invitation", "rfq_invitation__rfq_version__rfq", "principal__user").get(pk="f83ba13d-b9cf-45a3-ac94-8e0cfb80eef0")
    i = g.portal_invitation
    save("PORTAL_ENTRY.json", {"old_grant": g.pk, "old_invitation": i.pk, "expires_at": i.expires_at, "rfq_invitation": g.rfq_invitation_id, "rfq": g.rfq_invitation.rfq_version.rfq_id, "rfq_status": g.rfq_invitation.rfq_version.rfq.status, "closing_at": g.rfq_invitation.rfq_version.closing_at, "actor": g.principal.user.username})
    print("Development guard PASS; entry/source/data fingerprints saved.")
