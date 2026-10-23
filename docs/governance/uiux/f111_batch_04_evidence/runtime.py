"""Bounded BATCH-04 Development controls. Secrets never enter evidence."""

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

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
support = runpy.run_path(
    str(OUT.parent / "f111_batch_02_evidence/runtime_retest.py"),
    run_name="batch04_support",
)
snapshot = support["snapshot"]


class Parsed(support["Parsed"]):
    def handle_starttag(self, tag, attrs):
        attrs = [
            (
                key,
                value + " text-red-700"
                if key == "class" and "erp-field-error" in value
                else value,
            )
            for key, value in attrs
        ]
        super().handle_starttag(tag, attrs)


save = lambda name, value: (OUT / name).write_text(
    json.dumps(value, default=str, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)

from django.apps import apps
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone

from apps.accounts.models import User
from apps.organizations.authorization import (
    effective_role_assignments,
    effective_scope_grants,
    get_active_membership,
    has_business_permission,
)
from apps.organizations.models import Organization, OrganizationMembership
from apps.procurement.forms import GoodsReceiptForm
from apps.procurement.models import PurchaseOrder
from apps.procurement.services import (
    add_purchase_order_item,
    create_goods_receipt,
    create_purchase_order,
    issue_purchase_order,
)

MARKER = "B04-RUNTIME-PO-"
SITE_ACTOR = "uiux.reference.batch03.site-only"
BASE = "http://localhost:8007"
PATH = "/procurement/receipts/create/"


def authority():
    return [
        {
            "actor": m.user.username,
            "membership": str(m.pk),
            "organization": m.organization.slug,
            "roles": list(
                effective_role_assignments(m).values_list("role__code", flat=True)
            ),
            "grants": list(
                effective_scope_grants(m).values(
                    "id", "scope_type", "project__code", "site__code"
                )
            ),
            "receipt_capability": has_business_permission(
                user=m.user,
                organization=m.organization,
                permission="goods_receipts.create",
                allow_any_scope=True,
            ),
            "staff": m.user.is_staff,
            "superuser": m.user.is_superuser,
        }
        for m in OrganizationMembership.objects.filter(
            user__username__in=[
                "uiux.persona.project-manager",
                "uiux.persona.tenant-admin",
                SITE_ACTOR,
            ]
        ).select_related("organization", "user")
    ]


def preflight():
    executor = MigrationExecutor(connection)
    pending = executor.migration_plan(executor.loader.graph.leaf_nodes())
    assert not pending
    data = {
        "database": connection.settings_dict["NAME"],
        "host": "loopback",
        "settings": "config.settings.development",
        "pending_migrations": len(pending),
        "authority": authority(),
        "orders": list(
            PurchaseOrder.objects.filter(
                project__code__in=[
                    "PRJ-01-01",
                    "PRJ-01-02",
                    "PRJ-01-03",
                    "PRJ-01-04",
                    "PRJ-02-01",
                ]
            ).values(
                "id",
                "order_number",
                "status",
                "project__code",
                "current_version_id",
                "supplier_id",
            )
        ),
        "models": snapshot(),
    }
    save("RUNTIME_ENTRY.json", data)
    print("Development pending migrations:", len(pending))
    print(
        "Actors:",
        [
            {k: r[k] for k in ("actor", "roles", "grants", "receipt_capability")}
            for r in data["authority"]
        ],
    )
    print("Orders:", data["orders"])


def row_hashes():
    result = {}
    for model in apps.get_models():
        fields = [f.attname for f in model._meta.concrete_fields]
        if model._meta.label == "accounts.User":
            fields.remove("last_login")
        result[model._meta.label] = {
            str(row[model._meta.pk.attname]): support["digest"](row)
            for row in model._base_manager.values(*fields)
        }
    return result


def prepare():
    assert settings.SETTINGS_MODULE == "config.settings.development" and settings.DEBUG
    assert connection.settings_dict["NAME"] == "construction_erp"
    assert connection.settings_dict["HOST"] in {"localhost", "127.0.0.1", "::1"}
    assert not PurchaseOrder.objects.filter(order_number__startswith=MARKER).exists()
    actors = authority()
    site = next(a for a in actors if a["actor"] == SITE_ACTOR)
    assert site["receipt_capability"] and {g["scope_type"] for g in site["grants"]} == {
        "site"
    }
    assert not site["staff"] and not site["superuser"]
    save(
        "PREPARATION_BEFORE.json",
        {"authority": actors, "models": snapshot(), "rows": row_hashes()},
    )
    with connection.cursor() as cursor:
        cursor.execute("SET default_transaction_read_only = off")
    created = []
    with transaction.atomic():
        for key, code in zip(
            "ABCDX",
            ["PRJ-01-01", "PRJ-01-02", "PRJ-01-03", "PRJ-01-04", "PRJ-02-01"],
            strict=True,
        ):
            source = PurchaseOrder.objects.select_related(
                "project", "supplier", "organization"
            ).get(project__code=code, order_number__startswith="POR-")
            org = source.organization
            actor = User.objects.get(username=f"account.{org.slug}.owner")
            for permission in (
                "purchase_orders.create",
                "purchase_order_items.add",
                "purchase_orders.issue",
            ):
                assert has_business_permission(
                    user=actor,
                    organization=org,
                    permission=permission,
                    project=source.project,
                ), permission
            item = source.items.select_related("material").first()
            assert item is not None
            order = create_purchase_order(
                organization=org,
                actor=actor,
                project=source.project,
                supplier=source.supplier,
                order_number=MARKER + key,
                order_date=source.order_date,
                notes="Synthetic Development-only BATCH-04 source visibility control; no receipt or posting",
            )
            add_purchase_order_item(
                organization=org,
                actor=actor,
                purchase_order=order,
                material=item.material,
                quantity=__import__("decimal").Decimal("1"),
                unit_price=__import__("decimal").Decimal("1"),
            )
            order = issue_purchase_order(
                organization=org, actor=actor, purchase_order=order
            )
            created.append(
                {
                    "key": key,
                    "id": str(order.pk),
                    "number": order.order_number,
                    "label": str(order),
                    "project": code,
                    "organization": org.slug,
                    "actor": actor.username,
                    "status": order.status,
                    "version": str(order.current_version_id),
                }
            )
    after = authority()
    assert actors == after
    save(
        "FIXTURES.json",
        {
            "sources": created,
            "authority_before": actors,
            "authority_after": after,
            "temporary_authority": "NONE; reused persistent BATCH-03 site-only reference unchanged",
            "models": snapshot(),
        },
    )
    save(
        "RUNTIME_BEFORE.json",
        {"models": snapshot(), "rows": row_hashes(), "authority": after},
    )
    print(
        "Canonical synthetic issued orders:",
        len(created),
        "; existing site-only reference reused; authority unchanged",
    )


def sources():
    return {
        key: PurchaseOrder.objects.get(
            order_number=MARKER + key, status="issued", current_version__isnull=False
        )
        for key in "ABCDX"
    }


def payload(key):
    return {
        "purchase_order": str(sources()[key].pk),
        "receipt_number": "B04-NEGATIVE-ONLY",
        "received_at": "2026-10-22T10:00",
        "notes": "Synthetic rejected runtime control",
    }


def http():
    assert settings.SETTINGS_MODULE == "config.settings.development"
    assert connection.settings_dict["NAME"] == "construction_erp"
    with connection.cursor() as cursor:
        cursor.execute("SET default_transaction_read_only = off")
    records = []
    org = Organization.objects.get(slug="demo-construction-01")
    orders = sources()
    for alias, allowed in (
        ("uiux.persona.project-manager", "AB"),
        ("uiux.persona.tenant-admin", "ABCD"),
        (SITE_ACTOR, ""),
    ):
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
            return response.status, response.read().decode(), response.geturl()

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
        actor = User.objects.get(username=alias)
        member = get_active_membership(user=actor, organization=org)

        def observe(
            label,
            data=None,
            *,
            request=request,
            alias=alias,
            allowed=allowed,
            member=member,
        ):
            before = snapshot()
            status, body, url = request(PATH, data)
            parsed = Parsed(body)
            deltas = [
                name for name, value in snapshot().items() if value != before[name]
            ]
            leaks = [
                str(token)
                for key, order in orders.items()
                if key not in allowed
                for token in (order.pk, order.order_number, str(order))
                if str(token) in body
            ]
            expected = [
                {"value": str(value), "label": str(label)}
                for value, label in GoodsReceiptForm(
                    organization=org, membership=member
                )
                .fields["purchase_order"]
                .choices
            ]
            record = {
                "actor": alias,
                "label": label,
                "status": status,
                "method": "POST" if data else "GET",
                "options": parsed.fields.get("purchase_order"),
                "errors": parsed.errors,
                "forbidden_metadata": leaks,
                "model_deltas": deltas,
                "response_sha256": hashlib.sha256(body.encode()).hexdigest(),
                "real_authentication_csrf": True,
            }
            records.append(record)
            save("RUNTIME_HTTP.json", records)
            assert (
                status == 200
                and url == BASE + PATH
                and not leaks
                and set(deltas) <= {"sessions.Session"}
            ), record
            assert parsed.fields["purchase_order"] == expected, record
            actual = {row["value"] for row in parsed.fields["purchase_order"]}
            assert {str(orders[k].pk) for k in allowed} <= actual
            return parsed

        parsed = observe("GET")
        if alias == "uiux.persona.tenant-admin":
            continue
        for key in "CDX" if allowed else "ABCDX":
            data = payload(key)
            form = GoodsReceiptForm(data, organization=org, membership=member)
            assert not form.is_valid() and set(form.errors) == {"purchase_order"}
            parsed = observe(
                "forced " + key + " otherwise valid",
                data | {"csrfmiddlewaretoken": parsed.token},
            )
            assert parsed.errors
            before = snapshot()
            denied = False
            with transaction.atomic():
                try:
                    create_goods_receipt(
                        organization=org,
                        actor=actor,
                        purchase_order=orders[key],
                        receipt_number="B04-DIRECT-NEGATIVE",
                        received_at=timezone.now(),
                    )
                except PermissionDenied:
                    denied = True
                finally:
                    transaction.set_rollback(True)
            assert denied, "Direct service authorization failure"
            direct_deltas = [
                name for name, value in snapshot().items() if value != before[name]
            ]
            assert set(direct_deltas) <= {"sessions.Session"}, direct_deltas
        invalid = payload("B" if allowed else "A")
        invalid.pop("receipt_number")
        parsed = observe(
            "required-field redisplay", invalid | {"csrfmiddlewaretoken": parsed.token}
        )
        assert parsed.errors
        # Existing Purchase Order create stays scoped as a narrow known-good control.
        status, body, _ = request("/procurement/orders/create/")
        assert status == 200
        po = Parsed(body)
        keys = {row["value"] for row in po.fields["project"]}
        assert keys == (
            {str(orders[k].project_id) for k in "AB"} if allowed else {""}
        ) | ({""} if allowed else set())
    save(
        "HTTP_SUMMARY.json",
        {
            "observations": len(records),
            "service_scope_tenant_site_denials": 8,
            "purchase_order_regression": "PASS",
        },
    )
    print("Live HTTP observations PASS:", len(records))


def after():
    initial = json.loads((OUT / "RUNTIME_BEFORE.json").read_text(encoding="utf-8"))
    current = snapshot()
    deltas = [
        name for name, value in current.items() if value != initial["models"][name]
    ]
    assert set(deltas) <= {"sessions.Session"}, deltas
    assert support["digest"](authority()) == support["digest"](initial["authority"])
    prep = json.loads((OUT / "PREPARATION_BEFORE.json").read_text(encoding="utf-8"))
    rows = row_hashes()
    changed = [
        (model, pk)
        for model, records in prep["rows"].items()
        if model != "sessions.Session"
        for pk, value in records.items()
        if rows[model].get(pk) != value
    ]
    assert not changed, changed
    additions = {
        model: len(set(records) - set(prep["rows"][model]))
        for model, records in rows.items()
        if set(records) - set(prep["rows"][model])
    }
    assert set(additions) <= {
        "procurement.PurchaseOrder",
        "procurement.PurchaseOrderItem",
        "procurement.PurchaseOrderVersion",
        "procurement.PurchaseOrderVersionLine",
        "audit.AuditEvent",
        "sessions.Session",
    }, additions
    save("RUNTIME_AFTER.json", current)
    save(
        "RUNTIME_INTEGRITY.json",
        {
            "model_tables": len(current),
            "runtime_deltas": deltas,
            "preexisting_rows_changed": changed,
            "preparation_additions": additions,
            "authority_unchanged": True,
            "authority_fingerprint_before": support["digest"](initial["authority"]),
            "authority_fingerprint_after": support["digest"](authority()),
            "temporary_authority": "NONE; cleanup not required",
            "user_last_login_excluded": True,
            "receipts_created": 0,
        },
    )
    print(
        "Runtime integrity PASS:",
        len(current),
        "tables; prior rows preserved; authority unchanged",
    )


if __name__ == "__main__":
    if sys.argv[1] == "preflight":
        preflight()
    elif sys.argv[1] == "prepare":
        prepare()
    elif sys.argv[1] == "http":
        http()
    elif sys.argv[1] == "after":
        after()
