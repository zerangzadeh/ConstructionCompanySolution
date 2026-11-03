"""Read persisted local sample through installed Chrome; never mutate business rows."""

import json
import os
import subprocess
from pathlib import Path

from seed import OUT, ROOT, NUMBER, MARKER, verify_contract
from django.conf import settings
from django.contrib.sessions.models import Session
from django.db import connection
from django.test import Client

from apps.accounts.models import User
from apps.contracts.models import Contract
from apps.organizations.models import PlatformPolicyVersion
from apps.organizations.services import set_active_organization

assert settings.SETTINGS_MODULE == "config.settings.development" and settings.DEBUG
assert connection.settings_dict["HOST"] in ("localhost", "127.0.0.1", "::1", "")
result = json.loads((OUT / "result.json").read_text(encoding="utf-8"))
contract = Contract.objects.select_related("organization", "project").get(
    organization__slug="demo-construction-02", contract_number=NUMBER
)
assert MARKER in contract.notes
policy = PlatformPolicyVersion.objects.get(pk=result["policy_reused_unchanged"])
before = verify_contract(contract, policy)
owner = User.objects.get(username="account.demo-construction-02.owner", is_active=True)
client = Client(HTTP_HOST="localhost")
client.force_login(owner)
session = client.session
set_active_organization(session, contract.organization)
session.save()
session_key = session.session_key
out = OUT / "browser"
out.mkdir(exist_ok=True)
try:
    pages = [
        (
            "quantities",
            f"/contracts/{contract.pk}/?section=quantities",
            ["مقادیر و بهای قرارداد"],
        ),
        (
            "basis",
            result["baseline"]["path"],
            ["نسخه‌های مبنا", "مبنای متره و صورت‌وضعیت"],
        ),
        (
            "work-history",
            f"/billing/progress/?contract={contract.pk}",
            ["سوابق کارکرد", "مقدار کارکرد دوره", "کارکرد تجمعی تا این تاریخ"],
        ),
        ("claim-list", f"/billing/claims/?contract={contract.pk}", ["صورت‌وضعیت‌ها"]),
        (
            "work-detail",
            next(
                x["path"] for x in result["work_records"] if x["status"] == "verified"
            ),
            [
                "جزئیات کارکرد ثبت‌شده",
                "تاریخ انجام اندازه‌گیری",
                "کارکرد تجمعی تا این تاریخ",
            ],
        ),
        (
            "approved-claim",
            next(x["path"] for x in result["claims"] if x["status"] == "approved"),
            ["صورت‌وضعیت"],
        ),
    ]
    scenarios = []
    for width in (1440, 1024, 390):
        for name, path, text in pages:
            scenarios.append(
                {
                    "name": f"sample-{name}-{width}",
                    "path": path,
                    "width": width,
                    "mobile": width == 390,
                    "status": 200,
                    "screenshot": True,
                    "bottomScreenshot": True,
                    "noJsErrors": True,
                    "noHttpErrors": True,
                    "mustText": text,
                    "steps": [
                        {
                            "inspect": "document.documentElement.scrollWidth<=innerWidth+1",
                            "description": "Sample business content fits the document viewport",
                        }
                    ],
                }
            )
    for row in result["claims"]:
        if row["status"] == "approved":
            continue
        scenarios.append(
            {
                "name": f"sample-claim-{row['number']}-{row['revision']}-{row['status']}",
                "path": row["path"],
                "width": 1440,
                "status": 200,
                "screenshot": True,
                "noJsErrors": True,
                "noHttpErrors": True,
            }
        )
    env = os.environ.copy()
    env["MVP02_SESSION"] = session_key
    env["MVP02_SCENARIOS"] = json.dumps(scenarios)
    run = subprocess.run(
        [
            "node",
            str(ROOT / "scripts/verification/mvp02_browser.mjs"),
            "http://127.0.0.1:8000",
            str(out),
            "sample-review",
        ],
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=240,
        check=False,
    )
    (out / "command.txt").write_text(
        f"exit={run.returncode}\n{run.stderr}", encoding="utf-8"
    )
    if run.returncode:
        raise RuntimeError(run.stderr[-4000:])
    actual = json.loads(run.stdout)
    assert len(actual) == len(scenarios)
    after = verify_contract(contract, policy)
    assert before == after
    (OUT / "browser-verification.json").write_text(
        json.dumps(
            {
                "cases_passed": len(actual),
                "widths": [1440, 1024, 390],
                "business_records_unchanged": True,
                "business_verification": after,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print("Chrome sample checks PASS:", len(actual))
finally:
    Session.objects.filter(session_key=session_key).delete()
