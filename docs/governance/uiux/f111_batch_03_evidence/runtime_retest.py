"""BATCH-03 live Development negatives; no fixture or authorization writes."""

import hashlib
import json
import runpy
import subprocess
import sys
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener

OUT = Path(__file__).parent
ROOT = OUT.parents[3]
# Reuse the accepted read-only snapshot/parser functions without executing main.
support = runpy.run_path(
    str(OUT.parent / "f111_batch_02_evidence/runtime_retest.py"),
    run_name="batch03_readonly_support",
)
Parsed = support["Parsed"]
snapshot = support["snapshot"]

from django.conf import settings
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone

from apps.accounts.models import User
from apps.billing.forms import PayableCertificateForm, PayableMeasurementForm
from apps.contracts.models import Contract
from apps.organizations.authorization import (
    effective_role_assignments,
    effective_scope_grants,
    get_active_membership,
    has_business_permission,
)
from apps.organizations.models import Organization, OrganizationMembership

BASE = "http://127.0.0.1:8005"
LIMITED = "uiux.persona.project-manager"
POSITIVE = "uiux.persona.tenant-admin"
SURFACES = {
    "measurement": (PayableMeasurementForm, "contract_item"),
    "certificate": (PayableCertificateForm, "contract"),
}


def save(name, value):
    (OUT / name).write_text(
        json.dumps(value, ensure_ascii=False, default=str, indent=2) + "\n",
        encoding="utf-8",
    )


def fixtures():
    sources = {}
    for key, code in zip(
        "ABCDX",
        ["PRJ-01-01", "PRJ-01-02", "PRJ-01-03", "PRJ-01-04", "PRJ-02-01"],
        strict=True,
    ):
        contract = Contract.objects.get(
            project__code=code,
            contract_number__endswith="-05",
            direction="payable",
            contract_type="subcontract",
            status="active",
            deleted_at__isnull=True,
            party__isnull=False,
        )
        item = contract.items.order_by("sort_order").first()
        assert item is not None and item.organization_id == contract.organization_id
        sources[key] = (contract, item)
    return sources


def preflight():
    org = Organization.objects.get(slug="demo-construction-01")
    actors = []
    for alias in (LIMITED, POSITIVE):
        actor = User.objects.get(username=alias)
        member = get_active_membership(user=actor, organization=org)
        row = {
            "actor": alias,
            "membership": member.pk,
            "staff": actor.is_staff,
            "superuser": actor.is_superuser,
            "roles": list(
                effective_role_assignments(member).values_list("role__code", flat=True)
            ),
            "grants": list(
                effective_scope_grants(member).values(
                    "scope_type", "project__code", "site__code", "starts_at", "ends_at"
                )
            ),
            "permissions": {
                p: has_business_permission(
                    user=actor, organization=org, permission=p, allow_any_scope=True
                )
                for p in ("payable_measurements.record", "payable_certificates.create")
            },
        }
        assert not actor.is_staff and not actor.is_superuser
        assert all(row["permissions"].values())
        actors.append(row)
    assert {(g["scope_type"], g["project__code"]) for g in actors[0]["grants"]} == {
        ("project", "PRJ-01-01"),
        ("project", "PRJ-01-02"),
    }
    site_only = []
    for member in OrganizationMembership.objects.filter(
        status="active", user__is_active=True
    ).select_related("organization", "user"):
        grants = list(
            effective_scope_grants(member).values_list("scope_type", flat=True)
        )
        if grants and set(grants) == {"site"}:
            site_only.append(
                {
                    "membership": member.pk,
                    "organization": member.organization_id,
                    "required_capabilities": [
                        has_business_permission(
                            user=member.user,
                            organization=member.organization,
                            permission=p,
                            allow_any_scope=True,
                        )
                        for p in (
                            "payable_measurements.record",
                            "payable_certificates.create",
                        )
                    ],
                }
            )
    executor = MigrationExecutor(connection)
    pending = len(executor.migration_plan(executor.loader.graph.leaf_nodes()))
    assert pending == 0
    return {
        "at": timezone.now(),
        "settings": settings.SETTINGS_MODULE,
        "database": connection.settings_dict["NAME"],
        "host": "loopback",
        "pending_migrations": pending,
        "actors": actors,
        "qualifying_sources": {
            key: {
                "contract": str(contract.pk),
                "number": contract.contract_number,
                "title": contract.title,
                "contract_label": str(contract),
                "item": str(item.pk),
                "item_label": str(item),
                "description": item.description,
                "project": contract.project.code,
                "organization": str(contract.organization_id),
                "direction": contract.direction,
                "type": contract.contract_type,
                "status": contract.status,
                "deleted": contract.deleted_at,
                "item_order": item.sort_order,
            }
            for key, (contract, item) in fixtures().items()
        },
        "site_only_membership_candidates_all_tenants": site_only,
        "site_only_runtime": "PENDING_NO_EXISTING_QUALIFYING_ACTOR"
        if not site_only
        else "REQUIRES_CANDIDATE_REVIEW",
        "persistent_fixture_or_authority_preparation": "NOT_AUTHORIZED_NOT_PERFORMED",
    }


def payload(surface, contract, item):
    if surface == "measurement":
        return {
            "contract_item": str(item.pk),
            "measured_on": "2026-10-22",
            "period_quantity": "1",
            "cumulative_quantity": "1",
            "evidence_reference": "BATCH-03 runtime negative only",
        }
    return {
        "contract": str(contract.pk),
        "period_start": "2026-10-01",
        "period_end": "2026-10-31",
        "measurement_cutoff": "2026-10-22",
    }


def http():
    sources = fixtures()
    org = Organization.objects.get(slug="demo-construction-01")
    records = []
    for alias in (LIMITED, POSITIVE):
        actor = User.objects.get(username=alias)
        member = get_active_membership(user=actor, organization=org)
        opener = build_opener(HTTPCookieProcessor(CookieJar()))

        def request(path, data=None, *, opener=opener):
            req = Request(
                BASE + path,
                data=None if data is None else urlencode(data).encode(),
                headers={"Referer": BASE + path},
            )
            try:
                response = opener.open(req, timeout=30)
            except HTTPError as exc:
                response = exc
            return response.status, response.read().decode("utf-8"), response.geturl()

        _, body, _ = request("/accounts/login/")
        command = (
            "$c=Import-Clixml -LiteralPath ($env:LOCALAPPDATA+'/BONIRA/UIUXRuntimeAudit/credentials/"
            + alias
            + ".clixml'); $c.GetNetworkCredential().Password"
        )
        secret = subprocess.run(
            [
                r"C:\Users\azera\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\powershell\pwsh.exe",
                "-NoProfile",
                "-Command",
                command,
            ],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        status, body, url = request(
            "/accounts/login/",
            {
                "username": alias,
                "password": secret,
                "csrfmiddlewaretoken": Parsed(body).token,
            },
        )
        del secret
        assert status == 200 and "/accounts/login/" not in url and alias in body
        for surface, (form_class, field) in SURFACES.items():
            path = f"/billing/payable-{'measurements' if surface == 'measurement' else 'certificates'}/new/"
            forbidden_keys = "CDX" if alias == LIMITED else "X"
            expected = list(
                form_class(organization=org, membership=member).fields[field].choices
            )
            expected = [
                {"value": str(value), "label": str(label)} for value, label in expected
            ]

            def observe(
                label,
                data=None,
                *,
                path=path,
                forbidden_keys=forbidden_keys,
                alias=alias,
                surface=surface,
                field=field,
                expected=expected,
                request=request,
            ):
                before = snapshot()
                status, body, url = request(path, data)
                parsed = Parsed(body)
                after = snapshot()
                deltas = [name for name in before if before[name] != after[name]]
                forbidden = []
                for key in forbidden_keys:
                    contract, item = sources[key]
                    forbidden.extend(
                        [
                            str(contract.pk),
                            contract.contract_number,
                            str(item.pk),
                            str(contract),
                            str(item),
                        ]
                    )
                    # Repeated demo titles/descriptions cannot prove project provenance.
                    for text, index, attr in (
                        (contract.title, 0, "title"),
                        (item.description, 1, "description"),
                    ):
                        if all(text != getattr(sources[k][index], attr) for k in "AB"):
                            forbidden.append(text)
                exposed = [token for token in forbidden if token in body]
                record = {
                    "actor": alias,
                    "surface": surface,
                    "label": label,
                    "method": "POST" if data else "GET",
                    "status": status,
                    "options": parsed.fields.get(field),
                    "errors": parsed.errors,
                    "forbidden_metadata_matches": exposed,
                    "model_deltas": deltas,
                    "response_sha256": hashlib.sha256(body.encode()).hexdigest(),
                    "actual_login_and_csrf": True,
                }
                records.append(record)
                save("RUNTIME_HTTP.json", records)
                assert status == 200 and url == BASE + path
                assert not deltas and not exposed, record
                assert parsed.fields[field] == expected, record
                return parsed

            parsed = observe("authorized GET")
            for key in "AB" if alias == LIMITED else "ABCD":
                source = sources[key][1 if surface == "measurement" else 0]
                assert str(source.pk) in {
                    option["value"] for option in parsed.fields[field]
                }
            if alias == POSITIVE:
                continue
            base = payload(surface, *sources["B"])
            valid = form_class(base, organization=org, membership=member)
            assert valid.is_valid(), valid.errors
            for key in "CDX":
                data = base | {
                    field: str(sources[key][1 if surface == "measurement" else 0].pk)
                }
                rejected = form_class(data, organization=org, membership=member)
                assert not rejected.is_valid() and set(rejected.errors) == {field}
                parsed = observe(
                    f"forced {key} source; otherwise valid form",
                    data | {"csrfmiddlewaretoken": parsed.token},
                )
                assert parsed.errors
            invalid = dict(base)
            invalid.pop("measured_on" if surface == "measurement" else "period_start")
            parsed = observe(
                "missing required field redisplay",
                invalid | {"csrfmiddlewaretoken": parsed.token},
            )
            assert parsed.errors
    print("Live HTTP controls PASS:", len(records))


if __name__ == "__main__":
    if sys.argv[1] == "before":
        state = preflight()
        save("RUNTIME_BEFORE.json", state | {"models": snapshot()})
        print(
            "Qualifying A/B/C/D/X sources: PASS; site-only:", state["site_only_runtime"]
        )
    elif sys.argv[1] == "http":
        http()
    elif sys.argv[1] == "after":
        before = json.loads((OUT / "RUNTIME_BEFORE.json").read_text(encoding="utf-8"))
        after = snapshot()
        deltas = [name for name in after if after[name] != before["models"][name]]
        assert set(deltas) <= {"sessions.Session"}, deltas
        save("RUNTIME_AFTER.json", after)
        save(
            "RUNTIME_INTEGRITY.json",
            {
                "models_compared": len(after),
                "deltas": deltas,
                "user_last_login_excluded": True,
                "business_audit_authority_unchanged": True,
            },
        )
        print("All-model runtime integrity PASS:", len(after), "tables")
