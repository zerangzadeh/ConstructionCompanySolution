"""BATCH-03 canonical site-only Development actor and missing runtime controls."""

import hashlib
import json
import os
import re
import runpy
import secrets
import subprocess
import sys
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).parent
PRIOR = OUT.parent / "f111_batch_03_evidence"
support = runpy.run_path(str(PRIOR / "runtime_retest.py"), run_name="closure_support")
Parsed, snapshot = support["Parsed"], support["snapshot"]

from django.apps import apps
from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.db import connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.services import initialize_personal_password
from apps.organizations.access_services import (
    assign_membership_role,
    grant_membership_scope,
)
from apps.organizations.authorization import (
    effective_role_assignments,
    effective_scope_grants,
    get_active_membership,
    has_business_permission,
    membership_has_scope,
    membership_permission_codes,
)
from apps.organizations.models import (
    BusinessPermissionCode,
    Organization,
    OrganizationMembership,
    OrganizationRole,
)
from apps.organizations.services import create_organization_account
from apps.projects.models import ProjectSite

ALIAS = "uiux.reference.batch03.site-only"
BASE = "http://localhost:8006"
POWERSHELL = r"C:\Users\azera\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\powershell\pwsh.exe"
REASON = "BATCH_03_SITE_ONLY_RUNTIME_REFERENCE: Development-only persistent reference; one SITE scope; no Project/Organization grant"
NEEDED = {"payable_measurements.record", "payable_certificates.create"}
CREDENTIAL = (
    Path(os.environ["LOCALAPPDATA"])
    / "BONIRA/UIUXRuntimeAudit/credentials"
    / f"{ALIAS}.clixml"
)


def save(name, value):
    (OUT / name).write_text(
        json.dumps(value, ensure_ascii=False, default=str, sort_keys=True, indent=2)
        + "\n",
        encoding="utf-8",
    )


def read(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def digest(value):
    return hashlib.sha256(
        json.dumps(value, default=str, sort_keys=True).encode()
    ).hexdigest()


def git(*arguments):
    return subprocess.check_output(["git", *arguments], cwd=ROOT).decode()


def file_hashes():
    return {
        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        for name in git(
            "ls-files", "--cached", "--others", "--exclude-standard"
        ).splitlines()
        if (ROOT / name).is_file()
        and not name.startswith(
            "docs/governance/uiux/f111_batch_03_runtime_closure_evidence/"
        )
    }


def guard():
    assert settings.SETTINGS_MODULE == "config.settings.development" and settings.DEBUG
    assert connection.vendor == "postgresql"
    assert connection.settings_dict["HOST"] in {"localhost", "127.0.0.1", "::1"}
    assert connection.settings_dict["NAME"] == "construction_erp"


def authority(member):
    member = OrganizationMembership.objects.select_related("user", "organization").get(
        pk=member.pk
    )
    row = {
        "identity": {
            "id": member.user_id,
            "username": member.user.username,
            "active": member.user.is_active,
            "staff": member.user.is_staff,
            "superuser": member.user.is_superuser,
            "must_change_password": member.user.must_change_password,
        },
        "membership": {
            "id": member.pk,
            "organization": member.organization_id,
            "status": member.status,
            "legacy_role": member.role,
            "role_definition": member.role_definition_id,
            "authorization_migrated_at": member.authorization_migrated_at,
            "authorization_quarantined_at": member.authorization_quarantined_at,
        },
        "role_assignments": list(
            effective_role_assignments(member).values(
                "id",
                "role__code",
                "role_id",
                "assigned_by_id",
                "approved_by_id",
                "starts_at",
                "ends_at",
                "reason",
            )
        ),
        "capability_set": sorted(membership_permission_codes(member)),
        "scope_grants": list(
            effective_scope_grants(member).values(
                "id",
                "scope_type",
                "project_id",
                "site_id",
                "granted_by_id",
                "approved_by_id",
                "starts_at",
                "ends_at",
                "reason",
            )
        ),
        "required_capabilities": {
            permission: has_business_permission(
                user=member.user,
                organization=member.organization,
                permission=permission,
                allow_any_scope=True,
            )
            for permission in sorted(NEEDED)
        },
    }
    # Serialize UUID/date values consistently before fingerprinting across stages.
    row = json.loads(json.dumps(row, default=str))
    return row | {"authority_fingerprint": digest(row)}


def site_actor_candidates(org):
    rows = []
    for member in OrganizationMembership.objects.filter(
        organization=org,
        status="active",
        user__is_active=True,
        user__is_staff=False,
        user__is_superuser=False,
    ).select_related("user", "organization"):
        grants = list(
            effective_scope_grants(member).values_list("scope_type", flat=True)
        )
        if (
            grants
            and set(grants) == {"site"}
            and NEEDED <= set(membership_permission_codes(member))
        ):
            rows.append(authority(member))
    return rows


def reference():
    selected = read("PROVISIONING.json")["reference_username"]
    user = User.objects.get(username=selected)
    org = Organization.objects.get(slug="demo-construction-01")
    member = get_active_membership(user=user, organization=org)
    state = authority(member)
    assert not state["identity"]["staff"] and not state["identity"]["superuser"]
    assert all(state["required_capabilities"].values())
    assert {grant["scope_type"] for grant in state["scope_grants"]} == {"site"}
    assert not membership_has_scope(member)
    assert not membership_has_scope(
        member, project=support["fixtures"]()["A"][0].project
    )
    return user, org, member, state


def entry():
    assert not (OUT / "ENTRY.json").exists(), "Do not overwrite grounding"
    accepted_index = json.loads((PRIOR / "INDEX.json").read_text(encoding="utf-8"))
    drift = [
        name
        for name, expected in accepted_index.items()
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != expected
    ]
    assert not drift, drift
    current = file_hashes()
    old_entry = json.loads((PRIOR / "ENTRY.json").read_text(encoding="utf-8"))
    allowed_prior = {
        "apps/billing/forms.py",
        "apps/billing/views.py",
        "docs/governance/uiux/UIUX_FINDINGS_REGISTER.yaml",
    }
    source_drift = [
        name
        for name, expected in old_entry["hashes"].items()
        if name not in allowed_prior and current.get(name) != expected
    ]
    assert not source_drift, source_drift
    register = (ROOT / "docs/governance/uiux/UIUX_FINDINGS_REGISTER.yaml").read_text(
        encoding="utf-8"
    )
    for finding in ("121", "122"):
        block = re.search(
            rf"(?ms)^- finding_id: UIUX-F-{finding}\n.*?(?=^- finding_id:|\Z)", register
        ).group()
        assert (
            "finding_status: RESOLVED" in block
            and "runtime_status: RUNTIME_VERIFIED_RESOLVED" in block
        )
    org = Organization.objects.get(slug="demo-construction-01")
    candidates = site_actor_candidates(org)
    roles = []
    for role in OrganizationRole.objects.filter(is_active=True):
        permissions = set(
            role.permissions.filter(is_active=True).values_list("code", flat=True)
        )
        if role.organization_id in (None, org.pk) and NEEDED <= permissions:
            roles.append(
                {
                    "id": role.pk,
                    "code": role.code,
                    "permission_count": len(permissions),
                    "capability_set": sorted(permissions),
                }
            )
    roles.sort(key=lambda r: (r["permission_count"], r["code"]))
    assert roles and roles[0]["code"] == "operations_manager"
    writer = get_active_membership(
        user=User.objects.get(username="account.demo-construction-01.owner"),
        organization=org,
    )
    approver = get_active_membership(
        user=User.objects.get(username="uiux.persona.tenant-admin"), organization=org
    )
    for member in (writer, approver):
        for permission in (
            BusinessPermissionCode.AUTHORIZATION_ROLES_ASSIGN,
            BusinessPermissionCode.AUTHORIZATION_GRANTS_CREATE,
        ):
            assert has_business_permission(
                user=member.user, organization=org, permission=permission
            )
    assert has_business_permission(
        user=writer.user,
        organization=org,
        permission=BusinessPermissionCode.ACCOUNTS_CREATE,
    )
    assert set(roles[0]["capability_set"]) <= set(membership_permission_codes(writer))
    executor = MigrationExecutor(connection)
    assert not executor.migration_plan(executor.loader.graph.leaf_nodes())
    state = {
        "at": timezone.now(),
        "branch": git("branch", "--show-current").strip(),
        "head": git("rev-parse", "HEAD").strip(),
        "upstream": git("rev-parse", "@{u}").strip(),
        "divergence": git("rev-list", "--left-right", "--count", "HEAD...@{u}").strip(),
        "dirty": git("status", "--short"),
        "diff_names": git("diff", "--name-status"),
        "diff_stat": git("diff", "--stat"),
        "accepted_evidence_drift": drift,
        "other_original_file_drift": source_drift,
        "hashes": current,
        "settings": settings.SETTINGS_MODULE,
        "database": connection.settings_dict["NAME"],
        "pending_migrations": 0,
        "batch01_batch02": "RUNTIME_VERIFIED_RESOLVED",
        "existing_qualifying_site_actors": candidates,
        "canonical_role_candidates": roles,
        "selected_existing_role": roles[0],
        "writer": authority(writer),
        "independent_approver": authority(approver),
        "reference_before": list(
            User.objects.filter(username=ALIAS).values(
                "id", "username", "is_staff", "is_superuser", "is_active"
            )
        ),
        "authorized_touch_set": [
            "new BATCH-03 runtime closure report and evidence",
            "UIUX-F-123/UIUX-F-124 current closure metadata only",
            "minimum canonical Development reference identity and role/site assignment plus canonical audit/quarantine/authentication history",
        ],
        "accepted_tests_and_runtime_repeated": False,
    }
    assert state["branch"] == "main"
    save("ENTRY.json", state)
    (OUT / "REGISTER_BEFORE.txt").write_bytes(
        (ROOT / "docs/governance/uiux/UIUX_FINDINGS_REGISTER.yaml").read_bytes()
    )
    save("MODELS_BEFORE.json", snapshot())
    print(
        "Accepted evidence/source drift NONE; site-only candidates:",
        len(candidates),
        "; canonical role operations_manager eligible",
    )


def provision():
    initial = read("ENTRY.json")
    assert not (OUT / "PROVISIONING.json").exists(), "Do not duplicate provisioning"
    org = Organization.objects.get(slug="demo-construction-01")
    candidates = site_actor_candidates(org)
    if candidates:
        chosen = candidates[0]
        save(
            "PROVISIONING.json",
            {
                "reference_username": chosen["identity"]["username"],
                "created": False,
                "authority_after": chosen,
                "new_model_rows": {},
            },
        )
        return
    assert (
        not initial["reference_before"]
        and not User.objects.filter(username=ALIAS).exists()
    )
    assert not CREDENTIAL.exists()
    writer = User.objects.get(username="account.demo-construction-01.owner")
    approver = get_active_membership(
        user=User.objects.get(username="uiux.persona.tenant-admin"), organization=org
    )
    role = OrganizationRole.objects.get(pk=initial["selected_existing_role"]["id"])
    site = ProjectSite.objects.get(
        project__code="PRJ-01-01",
        code="SITE-01",
        is_active=True,
    )
    temporary, password = secrets.token_urlsafe(40), secrets.token_urlsafe(40)
    labels = {
        "accounts.User",
        "organizations.OrganizationMembership",
        "organizations.MembershipRoleAssignment",
        "organizations.MembershipScopeGrant",
        "organizations.AuthorizationMigrationIssue",
        "audit.AuditEvent",
    }
    before_ids = {
        label: set(apps.get_model(label)._base_manager.values_list("pk", flat=True))
        for label in labels
    }
    with connection.cursor() as cursor:
        cursor.execute("SET default_transaction_read_only = off")
    with transaction.atomic():
        user, member = create_organization_account(
            organization=org,
            actor=writer,
            username=ALIAS,
            temporary_password=temporary,
            role=role,
        )
        quarantined = authority(member)
        assignment = assign_membership_role(
            organization=org,
            actor=writer,
            membership_id=member.pk,
            role=role,
            approver_membership_id=approver.pk,
            reason=REASON,
        )
        assigned = authority(member)
        grant = grant_membership_scope(
            organization=org,
            actor=writer,
            membership_id=member.pk,
            scope_type="site",
            project=site.project,
            site=site,
            approver_membership_id=approver.pk,
            reason=REASON,
        )
        validate_password(password, user=user)
        initialize_personal_password(user=user, new_password=password)
        established = authority(member)
        assert all(established["required_capabilities"].values())
        assert {g["scope_type"] for g in established["scope_grants"]} == {"site"}
        assert (
            not established["identity"]["staff"]
            and not established["identity"]["superuser"]
        )
        assert (
            len(established["role_assignments"])
            == len(established["scope_grants"])
            == 1
        )
        # User-protected credential, outside repo/evidence; plaintext stays in memory/stdin.
        CREDENTIAL.parent.mkdir(parents=True, exist_ok=True)
        code = (
            "$p=[Console]::In.ReadToEnd(); $s=ConvertTo-SecureString $p -AsPlainText -Force; $c=[PSCredential]::new('"
            + ALIAS
            + "',$s); $c | Export-Clixml -LiteralPath '"
            + str(CREDENTIAL).replace("'", "''")
            + "'"
        )
        subprocess.run(
            [POWERSHELL, "-NoProfile", "-Command", code],
            input=password,
            text=True,
            capture_output=True,
            check=True,
        )
    del temporary, password
    with connection.cursor() as cursor:
        cursor.execute("SET default_transaction_read_only = on")
    new_rows = {
        label: sorted(
            str(pk)
            for pk in set(
                apps.get_model(label)._base_manager.values_list("pk", flat=True)
            )
            - before_ids[label]
        )
        for label in labels
    }
    save(
        "PROVISIONING.json",
        {
            "created": True,
            "reference_username": ALIAS,
            "identity_before": "ABSENT",
            "after_account_creation_quarantined": quarantined,
            "after_role_assignment_quarantined": assigned,
            "authority_after": established,
            "role_assignment_id": assignment.pk,
            "scope_grant_id": grant.pk,
            "site": {"id": site.pk, "code": site.code, "project_id": site.project_id},
            "new_model_rows": new_rows,
            "credential_storage": "Current-user DPAPI-protected PSCredential outside repository/evidence; mandatory first-password initialization through canonical service",
            "canonical_services": [
                "create_organization_account",
                "assign_membership_role",
                "grant_membership_scope",
                "initialize_personal_password",
            ],
            "role_permission_catalogue_modified": False,
        },
    )
    save("MODELS_PROVISIONED.json", snapshot())
    print(
        "Canonical reference provisioned; one existing role, one SITE grant; no Project/Organization grants"
    )


def get_secret(alias):
    credential = CREDENTIAL.parent / f"{alias}.clixml"
    code = (
        "$c=Import-Clixml -LiteralPath '"
        + str(credential).replace("'", "''")
        + "'; $c.GetNetworkCredential().Password"
    )
    return subprocess.run(
        [POWERSHELL, "-NoProfile", "-Command", code],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def runtime():
    user, org, member, state = reference()
    assert (
        state["authority_fingerprint"]
        == read("PROVISIONING.json")["authority_after"]["authority_fingerprint"]
    )
    save("RUNTIME_BEFORE.json", {"authority": state, "models": snapshot()})
    sources = support["fixtures"]()
    opener = build_opener(HTTPCookieProcessor(CookieJar()))

    def request(path, data=None):
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
    password = get_secret(user.username)
    status, body, url = request(
        "/accounts/login/",
        {
            "username": user.username,
            "password": password,
            "csrfmiddlewaretoken": Parsed(body).token,
        },
    )
    del password
    assert status == 200 and "/accounts/login/" not in url and user.username in body
    records = []
    for surface, (form_class, field) in support["SURFACES"].items():
        path = f"/billing/payable-{'measurements' if surface == 'measurement' else 'certificates'}/new/"

        def observe(label, data=None, *, path=path, surface=surface, field=field):
            before = snapshot()
            status, body, url = request(path, data)
            parsed = Parsed(body)
            after = snapshot()
            deltas = [label for label in before if before[label] != after[label]]
            # Enumerate every eligible source, including granted site's parent and its sibling line.
            tokens = []
            for contract, item in sources.values():
                tokens.extend(
                    [
                        str(contract.pk),
                        str(contract),
                        contract.contract_number,
                        str(item.pk),
                        str(item),
                        contract.title,
                        item.description,
                    ]
                )
                for sibling in contract.items.all():
                    tokens.extend([str(sibling.pk), str(sibling), sibling.description])
            exposed = sorted({text for text in tokens if text and text in body})
            record = {
                "surface": surface,
                "label": label,
                "method": "POST" if data else "GET",
                "status": status,
                "options": parsed.fields.get(field),
                "errors": parsed.errors,
                "forbidden_source_metadata_matches": exposed,
                "model_deltas": deltas,
                "response_sha256": hashlib.sha256(body.encode()).hexdigest(),
                "actual_login_and_csrf_middleware": True,
            }
            records.append(record)
            save("RUNTIME_HTTP.json", records)
            assert status == 200 and url == BASE + path
            assert parsed.fields[field] == [{"value": "", "label": "---------"}]
            assert not exposed and not deltas, record
            return parsed

        parsed = observe("site-only GET; no Project-owned sources")
        for key in "ABCDX":
            payload = support["payload"](surface, *sources[key])
            form = form_class(payload, organization=org, membership=member)
            assert not form.is_valid() and set(form.errors) == {field}, form.errors
            parsed = observe(
                f"forced {key} source; only source field invalid",
                payload | {"csrfmiddlewaretoken": parsed.token},
            )
            assert parsed.errors
        invalid = support["payload"](surface, *sources["A"])
        invalid.pop("measured_on" if surface == "measurement" else "period_start")
        parsed = observe(
            "missing required field plus unauthorized source redisplay",
            invalid | {"csrfmiddlewaretoken": parsed.token},
        )
        assert parsed.errors
    save("RUNTIME_AFTER_HTTP.json", {"authority": reference()[3], "models": snapshot()})
    print("Missing site-only HTTP controls PASS:", len(records))


def after():
    current = snapshot()
    runtime_before = read("RUNTIME_BEFORE.json")
    deltas = [
        label for label in current if current[label] != runtime_before["models"][label]
    ]
    assert set(deltas) <= {"sessions.Session"}, deltas
    state = reference()[3]
    assert state == runtime_before["authority"]
    provisioned = read("PROVISIONING.json")
    initial = read("MODELS_BEFORE.json")
    original_checks = {}
    # New canonical records are allowed; all pre-existing rows must stay identical.
    for model in apps.get_models():
        label = model._meta.label
        if label == "sessions.Session":
            continue
        new_ids = provisioned["new_model_rows"].get(label, [])
        fields = [f.attname for f in model._meta.concrete_fields]
        if label == "accounts.User":
            fields.remove("last_login")
        rows = list(
            model._base_manager.exclude(pk__in=new_ids)
            .order_by("pk")
            .values_list(*fields)
        )
        result = {"count": len(rows), "sha256": digest(rows)}
        assert result == initial[label], label
        original_checks[label] = "PASS"
    # M2M role/permission and user direct-authority relations are additional tables.
    save("RUNTIME_AFTER.json", {"authority": state, "models": current})
    save(
        "RUNTIME_VERIFICATION.json",
        {
            "runtime_models_compared": len(current),
            "runtime_deltas": deltas,
            "user_last_login_excluded": True,
            "authority_fingerprint_unchanged_since_provisioning": True,
            "preexisting_models_checked": len(original_checks),
            "all_preexisting_rows_unchanged": True,
            "new_canonical_rows": provisioned["new_model_rows"],
            "no_business_or_payable_mutation": True,
            "site_only_controls": "PASS",
            "accepted_p17_and_organization_actor_controls_repeated": False,
        },
    )
    print(
        "Runtime integrity PASS; all pre-existing rows unchanged; only canonical reference preparation and session bookkeeping"
    )


if __name__ == "__main__":
    guard()
    {"entry": entry, "provision": provision, "runtime": runtime, "after": after}[
        sys.argv[1]
    ]()
