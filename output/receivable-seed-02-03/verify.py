"""Read-only real Chrome verification of the explicitly authorized receivable seed."""

import hashlib
import json
import os
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
import django

django.setup()
from django.conf import settings
from django.test import Client

from apps.accounts.models import User
from apps.billing.models import ProgressClaim, ProgressRecord, ProjectBaseline
from apps.contracts.models import Contract
from apps.organizations.models import PlatformPolicyVersion
from apps.organizations.services import set_active_organization

HERE = Path(__file__).resolve().parent
assert settings.DEBUG and settings.SETTINGS_MODULE == "config.settings.development"
c = Contract.objects.select_related("organization").get(
    contract_number="UAT-REC-02-03",
    organization__slug="demo-construction-02",
    project__code="PRJ-02-03",
)
claims = list(
    ProgressClaim.objects.filter(contract=c).order_by("claim_number", "revision_number")
)
assert [(r.claim_number, r.revision_number, r.status) for r in claims] == [
    (1, 1, "approved"),
    (2, 1, "submitted"),
    (3, 1, "returned"),
    (3, 2, "draft"),
    (4, 1, "draft"),
]
for claim in claims:
    assert claim.gross_amount == sum(
        (i.current_amount for i in claim.items.all()), Decimal(0)
    )
    assert claim.net_amount == claim.gross_amount + sum(
        (i.amount for i in claim.adjustments.all()), Decimal(0)
    )
    if claim.status == "approved":
        assert claim.created_by_id != claim.approved_by_id
assert claims[2].returned_revision_id == claims[3].pk
assert (
    ProjectBaseline.objects.get(contract=c, status="approved").effective_ceiling
    == c.contract_value
)
assert (
    ProgressRecord.objects.filter(baseline__contract=c, status="verified").count() == 8
)


def fingerprint():
    data = {
        "contract": Contract.objects.filter(pk=c.pk).values().get(),
        "claims": list(
            ProgressClaim.objects.filter(contract=c).order_by("pk").values()
        ),
        "measurements": list(
            ProgressRecord.objects.filter(baseline__contract=c).order_by("pk").values()
        ),
        "baseline": list(ProjectBaseline.objects.filter(contract=c).values()),
        "policy": PlatformPolicyVersion.objects.values().get(
            pk=claims[0].regulatory_rule_version_id
        ),
    }
    return hashlib.sha256(
        json.dumps(data, sort_keys=True, default=str).encode()
    ).hexdigest()


before = fingerprint()
client = Client(HTTP_HOST="localhost")
client.force_login(
    User.objects.get(username="account.demo-construction-02.owner", is_active=True)
)
s = client.session
set_active_organization(s, c.organization)
s.save()
base = {"status": 200, "screenshot": True, "noJsErrors": True, "noHttpErrors": True}
check = "document.querySelectorAll('.cd-claims tbody tr').length===3 && Chart.getChart('contract-financial-chart').data.datasets.map(d=>d.data[0]).join(',')==='19620000000,29430000000,147150000000' && document.querySelector('.cd-progress-row:last-of-type progress').value===10 && [...document.querySelectorAll('.cd-claims tbody a')].every(a=>a.href.includes('/billing/claims/'))"
scenarios = [
    {
        **base,
        "name": "receivable-contract-" + str(width),
        "path": f"/contracts/{c.pk}/",
        "mobile": width == 390,
        "mustText": ["UAT-REC", "مبلغ تأییدشده"],
        "steps": [
            {
                "inspect": check,
                "description": "real seeded claims, 10 percent approved, exact ordinary approved/submitted/remaining amounts",
            }
        ],
    }
    for width in (1440, 390)
]
scenarios += [
    {
        **base,
        "name": f"claim-{r.claim_number}-revision-{r.revision_number}-{r.status}",
        "path": f"/billing/claims/{r.pk}/",
        "mustText": [r.get_status_display()],
    }
    for r in claims
]
env = os.environ.copy()
env["MVP02_SESSION"] = client.cookies["sessionid"].value
env["MVP02_SCENARIOS"] = json.dumps(scenarios)
result = subprocess.run(
    [
        "node",
        str(ROOT / "scripts/verification/mvp02_browser.mjs"),
        "http://127.0.0.1:8000",
        str(HERE / "browser"),
        "receivable-seed-owner",
    ],
    env=env,
    capture_output=True,
    text=True,
    encoding="utf-8",
    timeout=180,
    check=False,
)
if result.returncode:
    print((result.stderr or result.stdout)[-2500:], flush=True)
    raise SystemExit(result.returncode)
rows = json.loads(result.stdout)
assert before == fingerprint()
summary = {
    "contract_number": c.contract_number,
    "contract_path": f"/contracts/{c.pk}/",
    "claim_count": len(claims),
    "verified_measurements": 8,
    "scenarios": [
        {
            k: r.get(k)
            for k in ("name", "status", "width", "scroll", "jsErrors", "httpErrors")
        }
        for r in rows
    ],
    "before": before,
    "after": fingerprint(),
    "business_records_unchanged": True,
    "totals_and_revision_checks": "PASS",
}
(HERE / "verification.json").write_text(
    json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
)
print(json.dumps(summary, ensure_ascii=False), flush=True)
