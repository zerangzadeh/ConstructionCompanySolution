"""Actual CEP-012 migration proof in a new, disposable local PostgreSQL database.

Run with the repository's Development environment. No business database is opened:
credentials are reused against the administrative postgres database only to create
and remove the uniquely named proof database. Historical models/operations are
loaded by Django, not reconstructed SQL or mocked ORM calls.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import sys
from datetime import date, datetime, timezone
from decimal import Decimal
from importlib import import_module
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

import django

django.setup()

import psycopg
from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import connections, models, transaction
from django.db.migrations.loader import MigrationLoader
from psycopg import sql

OUT = ROOT / "docs/governance/cep/evidence/CEP-012_REQUALIFICATION_20261026"


def canonical(value):
    return json.dumps(value, cls=DjangoJSONEncoder, sort_keys=True)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def run(output_directory=OUT):
    output_directory.mkdir(parents=True, exist_ok=True)
    config = copy.deepcopy(settings.DATABASES["default"])
    assert settings.SETTINGS_MODULE == "config.settings.development"
    assert config["HOST"] in {"localhost", "127.0.0.1", "::1"}
    assert config["ENGINE"] == "django.db.backends.postgresql"
    name = "bonira_cep012_proof_" + uuid4().hex[:12]
    assert name != config["NAME"] and name.startswith("bonira_cep012_proof_")
    admin_options = dict(config.get("OPTIONS", {}))
    admin_options.update(
        dbname="postgres",
        user=config["USER"],
        password=config["PASSWORD"],
        host=config["HOST"],
        port=config["PORT"],
    )
    alias = "cep012_proof"
    proof = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "database": name,
        "configured_business_database_accessed": False,
        "fixture_kind": "SYNTHETIC_DEVELOPMENT_ONLY",
        "checks": [],
        "source_sha256": {
            path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
            for path in (
                "scripts/cep012_preservation_proof.py",
                "apps/audit/migrations/0016_membership_provisioned_action.py",
                "apps/billing/migrations/0006_tenantbillingconfiguration_and_more.py",
                "apps/billing/migrations/0008_p6_s01_s06_seed_reset_and_required_snapshots.py",
            )
        },
        "executed_operations": [
            "billing.0006: exact snapshot RenameField forward/backward; JSON preserved without reinterpretation",
            "audit.0016: preserve legacy events; AlterField(action)",
            "billing.0008: preflight reconciliation; four AlterField operations",
            "forward / retry / schema reverse / transactional rollback / reapply",
        ],
    }
    with psycopg.connect(**admin_options, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        try:
            config["NAME"] = name
            connections.databases[alias] = config
            connection = connections[alias]
            with connection.cursor() as cursor:
                cursor.execute("SELECT version(), current_database()")
                version, actual = cursor.fetchone()
                assert actual == name
                proof["postgresql"] = version
                # Same repository migration prerequisite, in the disposable DB.
                cursor.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
            loader = MigrationLoader(None)
            state = loader.project_state(
                [
                    ("billing", "0007_progressclaim_contract_term_version_and_more"),
                    ("subledgers", "0001_initial"),
                ]
            )
            selected = {}

            def include(model):
                if model._meta.label_lower in selected:
                    return
                selected[model._meta.label_lower] = model
                for field in (*model._meta.fields, *model._meta.local_many_to_many):
                    if field.is_relation:
                        include(field.remote_field.model)

            for app, model in [
                ("audit", "AuditEvent"),
                ("billing", "ProgressClaimItem"),
                ("billing", "ClaimAdjustment"),
                ("billing", "ClaimSettlementAllocation"),
                ("subledgers", "SettlementAllocation"),
            ]:
                include(state.apps.get_model(app, model))
            with connection.schema_editor() as editor:
                for model in selected.values():
                    editor.create_model(model)

            serial = 0

            def make(app, model, **overrides):
                nonlocal serial
                serial += 1
                cls = state.apps.get_model(app, model)
                values = {}
                for field in cls._meta.fields:
                    if field.name in overrides:
                        continue
                    if (
                        field.has_default()
                        or field.null
                        or isinstance(field, (models.AutoField, models.BigAutoField))
                        or getattr(field, "auto_now", False)
                        or getattr(field, "auto_now_add", False)
                    ):
                        continue
                    if field.is_relation:
                        raise AssertionError(
                            f"Explicit fixture link required: {model}.{field.name}"
                        )
                    if isinstance(field, models.DateTimeField):
                        values[field.name] = datetime(2026, 1, 15, tzinfo=timezone.utc)
                    elif isinstance(field, models.DateField):
                        values[field.name] = date(2026, 1, 15)
                    elif isinstance(field, models.DecimalField):
                        values[field.name] = Decimal(10)
                    elif isinstance(field, models.IntegerField):
                        values[field.name] = serial
                    elif isinstance(field, models.UUIDField):
                        values[field.name] = uuid4()
                    elif isinstance(field, models.JSONField):
                        values[field.name] = {"synthetic": True}
                    elif isinstance(field, models.BooleanField):
                        values[field.name] = False
                    elif field.blank:
                        values[field.name] = ""
                    else:
                        values[field.name] = f"synthetic-{serial}"
                values.update(overrides)
                return cls.objects.using(alias).create(**values)

            Audit = state.apps.get_model("audit", "AuditEvent")
            Claim = state.apps.get_model("billing", "ProgressClaim")
            user = make("accounts", "User", username="cep012-synthetic", password="!")
            fixtures = []
            for tenant in range(2):
                org = make("organizations", "Organization", slug=f"cep012-{tenant}")
                member = make(
                    "organizations",
                    "OrganizationMembership",
                    organization=org,
                    user=user,
                )
                project = make("projects", "Project", organization=org)
                contract = make(
                    "contracts", "Contract", organization=org, project=project
                )
                party = make(
                    "parties", "BusinessParty", organization=org, party_kind="legal"
                )
                identity = make(
                    "parties", "PartyIdentitySnapshot", organization=org, party=party
                )
                policy = make(
                    "organizations", "PlatformPolicy", created_by=user, updated_by=user
                )
                policy_version = make(
                    "organizations",
                    "PlatformPolicyVersion",
                    policy=policy,
                    created_by=user,
                )
                term = make(
                    "contracts",
                    "ContractTermVersion",
                    organization=org,
                    contract=contract,
                    created_by=user,
                )
                baseline = make(
                    "billing",
                    "ProjectBaseline",
                    organization=org,
                    contract=contract,
                    project=project,
                )
                common = {
                    "organization": org,
                    "project": project,
                    "contract": contract,
                    "baseline": baseline,
                    "currency_code": "IRR",
                    "contract_term_version": term,
                    "party_identity_snapshot": identity,
                    "regulatory_rule_version": policy_version,
                    "created_by": user,
                    "billing_configuration_snapshot": {"historical": tenant},
                    "calculation_snapshot": {"amount": "100.2500"},
                    "gross_amount": Decimal("100.2500"),
                    "net_amount": Decimal("90.1250"),
                }
                returned = make(
                    "billing",
                    "ProgressClaim",
                    **common,
                    claim_number=1,
                    revision_number=1,
                    status="returned",
                )
                claim = make(
                    "billing",
                    "ProgressClaim",
                    **common,
                    claim_number=1,
                    revision_number=2,
                    returned_revision=returned,
                    status="approved",
                    approved_by=user,
                    approved_at=datetime(2026, 1, 16, tzinfo=timezone.utc),
                )
                payment = make(
                    "payments",
                    "Payment",
                    organization=org,
                    project=project,
                    direction="outgoing",
                )
                allocation = make(
                    "payments",
                    "PaymentAllocation",
                    organization=org,
                    contract=contract,
                    payment=payment,
                )
                baseline_item = make(
                    "billing",
                    "BaselineItem",
                    organization=org,
                    baseline=baseline,
                    planned_quantity=Decimal(10),
                    unit_rate=Decimal(10),
                    planned_value=Decimal(100),
                )
                make(
                    "billing",
                    "ProgressClaimItem",
                    claim=claim,
                    baseline_item=baseline_item,
                    previous_cumulative_quantity=Decimal(0),
                    current_quantity=Decimal(1),
                    new_cumulative_quantity=Decimal(1),
                    unit_rate_snapshot=Decimal("100.25"),
                    current_amount=Decimal("100.25"),
                )
                make(
                    "billing",
                    "ClaimAdjustment",
                    claim=claim,
                    adjustment_type="retention",
                    amount=Decimal("10.125"),
                )
                settlement = make(
                    "billing",
                    "ClaimSettlementAllocation",
                    organization=org,
                    claim=claim,
                    payment_allocation=allocation,
                    amount=Decimal("10.25"),
                    status="reversed",
                    reversed_by=user,
                    reversed_at=datetime(2026, 1, 16, tzinfo=timezone.utc),
                    reversal_reason="synthetic retained reversal",
                    created_by=user,
                )
                movement = make(
                    "treasury",
                    "TreasuryMovement",
                    organization=org,
                    created_by=member,
                    kind="payment",
                )
                obligation = make(
                    "subledgers",
                    "Obligation",
                    organization=org,
                    recognized_by=member,
                    direction="payable",
                    source_kind="synthetic",
                    source_version=1,
                )
                make(
                    "subledgers",
                    "SettlementAllocation",
                    organization=org,
                    created_by=member,
                    obligation=obligation,
                    treasury_movement=movement,
                    amount=Decimal("10.125000"),
                )
                for action in (
                    "membership.invited",
                    "membership.accepted",
                    "project.created",
                ):
                    make(
                        "audit",
                        "AuditEvent",
                        organization=org,
                        actor=user,
                        action=action,
                        entity_type="synthetic",
                        entity_id=str(claim.pk),
                        metadata={"historical": tenant},
                    )
                fixtures.append((claim, identity, term, settlement))
            make(
                "audit",
                "AuditEvent",
                action="membership.invited",
                entity_type="platform",
                organization=None,
                actor=None,
            )

            def snapshot():
                return {
                    label: list(model.objects.using(alias).order_by("pk").values())
                    for label, model in selected.items()
                }

            def check(label, assertion):
                assert assertion, label
                proof["checks"].append({"check": label, "status": "PASS"})

            billing = import_module(
                "apps.billing.migrations.0008_p6_s01_s06_seed_reset_and_required_snapshots"
            )
            audit = import_module(
                "apps.audit.migrations.0016_membership_provisioned_action"
            )
            before = snapshot()
            snapshot_migration = import_module(
                "apps.billing.migrations.0006_tenantbillingconfiguration_and_more"
            )
            rename = next(
                operation
                for operation in snapshot_migration.Migration(
                    "0006", "billing"
                ).operations
                if type(operation).__name__ == "RenameField"
            )
            legacy_state = state.clone()
            legacy_state.rename_field(
                "billing",
                "progressclaim",
                "billing_configuration_snapshot",
                "policy_snapshot",
            )
            with connection.schema_editor() as editor:
                rename.database_backwards("billing", editor, state, legacy_state)
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT id,policy_snapshot FROM billing_progressclaim ORDER BY id"
                )
                legacy_payloads = {
                    str(key): json.loads(value) if isinstance(value, str) else value
                    for key, value in cursor.fetchall()
                }
            check(
                "legacy policy JSON and UUIDs retained at source checkpoint",
                legacy_payloads
                == {
                    str(row["id"]): row["billing_configuration_snapshot"]
                    for row in before["billing.progressclaim"]
                },
            )
            with connection.schema_editor() as editor:
                rename.database_forwards("billing", editor, legacy_state, state)
            check(
                "snapshot rename/reverse/reapply preserves every full row",
                before == snapshot(),
            )
            proof["source_counts"] = {k: len(v) for k, v in before.items()}
            proof["before_hash"] = digest(before)
            with connection.schema_editor() as editor:
                report = billing.preservation_report(state.apps, editor)
            proof["mapping"] = report["mapping"]
            check(
                "every eligible claim/allocation has identity target",
                len(report["mapping"]) == 6 and not report["exceptions"],
            )
            claim, identity, term, settlement = fixtures[0]
            for label, cls, source_id, change in [
                (
                    "missing_snapshot",
                    Claim,
                    claim.pk,
                    {"party_identity_snapshot_id": None},
                ),
                ("missing_term", Claim, claim.pk, {"contract_term_version_id": None}),
                ("missing_rule", Claim, claim.pk, {"regulatory_rule_version_id": None}),
                (
                    "foreign_tenant_snapshot",
                    Claim,
                    claim.pk,
                    {"party_identity_snapshot_id": fixtures[1][1].pk},
                ),
                (
                    "foreign_contract_term",
                    Claim,
                    claim.pk,
                    {"contract_term_version_id": fixtures[1][2].pk},
                ),
                ("missing_currency", Claim, claim.pk, {"currency_code": ""}),
                (
                    "foreign_revision",
                    Claim,
                    claim.pk,
                    {"returned_revision_id": fixtures[1][0].pk},
                ),
                (
                    "foreign_allocation",
                    type(settlement),
                    settlement.pk,
                    {"payment_allocation_id": fixtures[1][3].payment_allocation_id},
                ),
            ]:
                try:
                    with transaction.atomic(using=alias):
                        cls.objects.using(alias).filter(pk=source_id).update(**change)
                        invalid_before = snapshot()
                        with connection.schema_editor() as editor:
                            rejected = billing.preservation_report(state.apps, editor)
                        check(
                            label + " explicit exception",
                            any(
                                r["source"] == str(source_id)
                                for r in rejected["exceptions"]
                            ),
                        )
                        proof.setdefault("exception_cases", {})[label] = rejected[
                            "exceptions"
                        ]
                        try:
                            with connection.schema_editor() as editor:
                                billing.Migration("0008", "billing").apply(
                                    state, editor
                                )
                        except RuntimeError as error:
                            check(
                                label + " fail closed",
                                str(error).startswith(
                                    "CEP012 historical snapshot/reference"
                                ),
                            )
                        else:
                            raise AssertionError("Invalid fixture was not refused")
                        check(label + " source preserved", invalid_before == snapshot())
                        transaction.set_rollback(True, using=alias)
                finally:
                    check(
                        label + " rollback restores full source", before == snapshot()
                    )
            migration = billing.Migration("0008", "billing")
            for iteration in ("forward", "retry"):
                with connection.schema_editor() as editor:
                    migration.apply(state, editor)
                    audit.Migration("0016", "audit").apply(state, editor)
                check(
                    iteration
                    + " full rows, lineage, tenant, actors and authority unchanged",
                    before == snapshot(),
                )
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT column_name,is_nullable FROM information_schema.columns WHERE table_name='billing_progressclaim' AND column_name IN ('contract_term_version_id','party_identity_snapshot_id','regulatory_rule_version_id','currency_code') ORDER BY column_name"
                )
                proof["target_columns"] = cursor.fetchall()
            check(
                "target snapshot columns required",
                len(proof["target_columns"]) == 4
                and all(r[1] == "NO" for r in proof["target_columns"]),
            )
            with connection.schema_editor() as editor:
                migration.unapply(state, editor)
                audit.Migration("0016", "audit").unapply(state, editor)
            check("schema reverse preserves all source rows", before == snapshot())
            with transaction.atomic(using=alias):
                with connection.schema_editor() as editor:
                    migration.apply(state, editor)
                transaction.set_rollback(True, using=alias)
            check(
                "transactional rehearsal rollback preserves history",
                before == snapshot(),
            )
            with connection.schema_editor() as editor:
                migration.apply(state, editor)
                audit.Migration("0016", "audit").apply(state, editor)
            after = snapshot()
            check("reapply reconciles entire fixture", before == after)
            check(
                "legacy and platform audit history retained",
                Audit.objects.using(alias).count() == 7,
            )
            proof["after_counts"] = {k: len(v) for k, v in after.items()}
            proof["after_hash"] = digest(after)
            proof["audit_mapping"] = [
                {"source": str(r["id"]), "target": str(r["id"])}
                for r in before["audit.auditevent"]
            ]
            proof["status"] = "PASS"
        except BaseException as error:
            proof["status"] = "FAIL"
            proof["failure_type"] = type(error).__name__
            raise
        finally:
            if alias in connections:
                connections[alias].close()
            assert (
                name.startswith("bonira_cep012_proof_")
                and name != settings.DATABASES["default"]["NAME"]
            )
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))
            proof["disposable_database_removed"] = True
            proof["finished_at"] = datetime.now(timezone.utc).isoformat()
            (output_directory / "PRESERVATION.json").write_text(
                canonical(proof) + "\n", encoding="utf-8"
            )
    print(
        f"CEP012 preservation: {len(proof['checks'])} checks PASS; PostgreSQL; disposable database removed"
    )


if __name__ == "__main__":
    run()
