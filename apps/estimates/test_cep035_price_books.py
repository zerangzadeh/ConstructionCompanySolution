"""Synthetic source-engine tests; no official Iranian source activation evidence."""

import hashlib
import json
import os
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import SimpleTestCase, TestCase, TransactionTestCase

from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
from apps.estimates import models as m
from apps.estimates import services as legacy
from apps.estimates import test_p4_depth as depth_tests
from apps.estimates.price_books import (
    activate_price_book_version,
    create_price_book,
    import_price_book_version,
    map_estimate_price_book,
    parse_price_book_csv,
    reconcile_estimate_price_books,
)
from apps.materials.models import UnitOfMeasure
from apps.organizations.models import (
    AuthorizationScopeType,
    BusinessPermission,
    MembershipScopeGrant,
    Organization,
    OrganizationRole,
)
from apps.organizations.models import (
    BusinessPermissionCode as P,
)
from apps.projects.models import Project

CSV = "code,chapter,description,unit,value\nTEST-1,TEST,Synthetic test row,EA,12.3400\n"


class PriceBookFixture:
    def setUp(self):
        self.actor = User.objects.create_user(username="cep035-test")
        self.organization = Organization.objects.create(name="Synthetic", slug="cep035")
        self.role = OrganizationRole.objects.create(
            code="cep035-test", name="Explicit test grants"
        )
        self.role.permissions.set(BusinessPermission.objects.filter(is_active=True))
        self.membership = self.organization.memberships.create(
            user=self.actor,
            role="company_owner",
            role_definition=self.role,
            status="active",
        )
        MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=self.membership,
            scope_type=AuthorizationScopeType.ORGANIZATION,
            reason="Isolated CEP035 test",
        )
        self.unit = UnitOfMeasure.objects.create(
            organization=self.organization,
            code="EA",
            name="Synthetic unit",
            symbol="ea",
            category="count",
        )
        self.project = Project.objects.create(
            organization=self.organization, code="PB", name="Synthetic"
        )
        self.estimate = legacy.create_estimate(
            organization=self.organization,
            actor=self.actor,
            project=self.project,
            estimate_number="PB1",
            title="Synthetic",
        )
        self.item = legacy.add_estimate_item(
            estimate=self.estimate,
            actor=self.actor,
            description="Synthetic estimate item",
            quantity=Decimal(2),
            unit_price=Decimal(5),
            unit_of_measure=self.unit,
        )

    def book(self):
        return create_price_book(
            organization=self.organization,
            actor=self.actor,
            code="SYNTHETIC",
            name="Synthetic fixture",
            source_authority="TEST ONLY",
        )

    def version(self, book=None, number="1", **changes):
        arguments = {
            "organization": self.organization,
            "actor": self.actor,
            "book": book or self.book(),
            "version": number,
            "publication_year": "TEST-2026",
            "publication_reference": "TEST publication",
            "effective_from": date(2026, 1, 1),
            "effective_to": date(2026, 12, 31),
            "currency": "IRR",
            "source_reference": "TEST ONLY; no official source",
            "artifact_sha256": hashlib.sha256(CSV.encode()).hexdigest(),
            "content": CSV,
            "idempotency_key": "import-" + number,
        }
        return import_price_book_version(**(arguments | changes))

    def activate(self, version, **changes):
        return activate_price_book_version(
            **(
                {
                    "organization": self.organization,
                    "actor": self.actor,
                    "version": version,
                    "approval_reference": "SYNTHETIC TEST ATTESTATION ONLY",
                    "reviewed_artifact_sha256": version.artifact_sha256,
                    "reviewed_content_sha256": version.content_sha256,
                }
                | changes
            )
        )

    def mapping(self, row, item=None):
        return map_estimate_price_book(
            organization=self.organization,
            actor=self.actor,
            item=item or self.item,
            row=row,
            effective_date=date(2026, 10, 18),
            evidence_reference="Synthetic explicit selection",
        )


class PriceBookParserTests(SimpleTestCase):
    def test_strict_schema_finite_values_and_no_guessed_columns(self):
        self.assertEqual(parse_price_book_csv(CSV)[0]["value"], "12.3400")
        for content in (
            "",
            CSV.replace("chapter", "unknown"),
            CSV.replace("12.3400", "NaN"),
            CSV.replace("12.3400", "Infinity"),
            CSV.replace("12.3400", "-1"),
            CSV.replace("12.3400", "1.00001"),
            CSV.replace("TEST-1", "=A1"),
            CSV + CSV.splitlines()[1] + "\n",
        ):
            with self.subTest(content=content), self.assertRaises(ValidationError):
                parse_price_book_csv(content)


class PriceBookServiceTests(PriceBookFixture, TestCase):
    def test_import_provenance_idempotency_and_changed_request_rejection(self):
        book = self.book()
        version = self.version(book)
        self.assertEqual(self.version(book).pk, version.pk)
        self.assertEqual(version.rows.count(), 1)
        self.assertEqual(version.book.source_authority, "TEST ONLY")
        self.assertEqual(version.publication_year, "TEST-2026")
        self.assertFalse(m.PriceBookActivation.objects.exists())
        with self.assertRaises(ValidationError):
            self.version(book, content=CSV.replace("12.3400", "20"))
        self.assertEqual(
            AuditEvent.objects.filter(action=AuditAction.PRICE_BOOK_IMPORTED).count(), 1
        )

    def test_missing_source_or_unit_fails_atomically(self):
        book = self.book()
        for changes in (
            {"source_reference": ""},
            {"artifact_sha256": "invalid"},
            {"content": CSV.replace("EA", "UNKNOWN")},
            {"effective_to": date(2025, 1, 1)},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.version(book, **changes)
        self.assertFalse(m.PriceBookVersion.objects.exists())
        self.assertFalse(m.PriceBookRow.objects.exists())

    def test_activation_requires_exact_evidence_and_imported_row_set(self):
        version = self.version()
        for changes in (
            {"approval_reference": ""},
            {"reviewed_artifact_sha256": "0" * 64},
            {"reviewed_content_sha256": "0" * 64},
        ):
            with self.assertRaises(ValidationError):
                self.activate(version, **changes)
        activation = self.activate(version)
        self.assertEqual(self.activate(version).pk, activation.pk)
        with self.assertRaises(ValidationError):
            self.activate(version, approval_reference="replacement")
        with self.assertRaises(ValidationError):
            m.PriceBookRow.objects.create(
                organization=self.organization,
                created_by=self.membership,
                version=version,
                code="NEW",
                chapter="TEST",
                description="Cannot append",
                unit_of_measure=self.unit,
                value=Decimal(1),
            )

    def test_row_set_mismatch_prevents_activation(self):
        version = self.version()
        m.PriceBookRow.objects.create(
            organization=self.organization,
            created_by=self.membership,
            version=version,
            code="EXTRA",
            chapter="TEST",
            description="Unvalidated extra row",
            unit_of_measure=self.unit,
            value=Decimal(1),
        )
        with self.assertRaises(ValidationError):
            self.activate(version)
        self.assertFalse(m.PriceBookActivation.objects.exists())

    def test_mapping_inactive_and_wrong_effective_date_fail_closed(self):
        version = self.version()
        with self.assertRaises(ValidationError):
            self.mapping(version.rows.get())
        self.activate(version)
        with self.assertRaises(ValidationError):
            map_estimate_price_book(
                organization=self.organization,
                actor=self.actor,
                item=self.item,
                row=version.rows.get(),
                effective_date=date(2027, 1, 1),
                evidence_reference="Outside source window",
            )
        self.assertFalse(m.EstimatePriceBookMapping.objects.exists())

    def test_new_source_version_never_automatically_remaps_and_explicit_remap_retains_history(
        self,
    ):
        version = self.version()
        self.activate(version)
        first = self.mapping(version.rows.get())
        replacement = self.version(version.book, "2", supersedes=version)
        self.activate(replacement)
        self.item.refresh_from_db()
        self.assertEqual(self.item.price_book_mapping_id, first.pk)
        second = self.mapping(replacement.rows.get())
        self.assertEqual(second.identity, first.identity)
        self.assertEqual(second.version, 2)
        self.assertEqual(second.supersedes_id, first.pk)
        self.assertEqual(first.row.version_id, version.pk)
        self.item.refresh_from_db()
        self.assertEqual(self.item.unit_price, Decimal(5))
        for operation in (
            first.save,
            first.delete,
            lambda: m.EstimatePriceBookMapping.objects.update(version=99),
            lambda: m.PriceBookVersion.objects.all().delete(),
        ):
            with self.assertRaises(ValidationError):
                operation()

    def test_explicit_revision_retains_pinned_source_and_historical_reproducibility(
        self,
    ):
        version = self.version()
        self.activate(version)
        first = self.mapping(version.rows.get())
        legacy.approve_estimate(estimate=self.estimate, actor=self.actor)
        with self.assertRaises(ValidationError):
            self.mapping(version.rows.get())
        draft = legacy.create_estimate_revision(
            estimate=self.estimate, actor=self.actor
        )
        copied = draft.items.get()
        mapping = copied.price_book_mapping
        self.assertEqual(mapping.supersedes_id, first.pk)
        self.assertEqual(mapping.row_id, first.row_id)
        self.assertEqual(mapping.source_item_id, copied.pk)
        self.item.refresh_from_db()
        self.assertEqual(self.item.price_book_mapping_id, first.pk)
        self.assertEqual(copied.unit_price, self.item.unit_price)
        trace = reconcile_estimate_price_books(
            organization=self.organization, actor=self.actor, estimate=self.estimate
        )
        self.assertEqual(len(trace["items"]), 2)
        if path := os.environ.get("CEP035_TRACE_PATH"):
            Path(path).write_text(json.dumps(trace, indent=2), encoding="utf-8")

    def test_changed_draft_requires_explicit_mapping_before_approval(self):
        version = self.version()
        self.activate(version)
        self.mapping(version.rows.get())
        self.item.refresh_from_db()
        self.item.quantity = Decimal(3)
        self.item.save()
        with self.assertRaises(ValidationError):
            legacy.approve_estimate(estimate=self.estimate, actor=self.actor)
        self.mapping(version.rows.get())
        legacy.approve_estimate(estimate=self.estimate, actor=self.actor)

    def test_tenant_scope_permissions_and_default_grants(self):
        self.assertFalse(
            OrganizationRole.objects.filter(
                is_system=True,
                permissions__code__in=[
                    P.PRICE_BOOKS_MANAGE,
                    P.PRICE_BOOKS_ACTIVATE,
                    P.PRICE_BOOK_MAPPINGS_MANAGE,
                ],
            ).exists()
        )
        version = self.version()
        self.role.permissions.remove(
            BusinessPermission.objects.get(code=P.PRICE_BOOKS_ACTIVATE)
        )
        with self.assertRaises(PermissionDenied):
            self.activate(version)
        other = Organization.objects.create(name="Other", slug="other035")
        with self.assertRaises(PermissionDenied):
            import_price_book_version(
                organization=self.organization,
                actor=self.actor,
                book=m.PriceBook.objects.create(
                    organization=other,
                    created_by=other.memberships.create(
                        user=self.actor,
                        role="company_owner",
                        role_definition=self.role,
                        status="active",
                    ),
                    code="OTHER",
                    name="Other",
                    source_authority="TEST",
                ),
                version="bad",
                publication_year="TEST",
                publication_reference="TEST",
                effective_from=date(2026, 1, 1),
                effective_to=date(2026, 12, 31),
                currency="IRR",
                source_reference="TEST",
                artifact_sha256="0" * 64,
                content=CSV,
                idempotency_key="other",
            )
        MembershipScopeGrant.objects.filter(membership=self.membership).delete()
        with self.assertRaises(PermissionDenied):
            self.book()

    def test_audit_failure_rolls_back_import(self):
        book = self.book()
        with (
            patch(
                "apps.estimates.price_books.record_audit_event",
                side_effect=RuntimeError("injected"),
            ),
            self.assertRaises(RuntimeError),
        ):
            self.version(book)
        self.assertFalse(m.PriceBookVersion.objects.exists())


class PriceBookMigrationTests(PriceBookFixture, TransactionTestCase):
    def test_populated_legacy_sources_and_approved_history_survive_rollback_reapply(
        self,
    ):
        source = legacy.create_price_source(
            organization=self.organization,
            actor=self.actor,
            code="LEGACY",
            name="Legacy",
            version="1",
            source_reference="legacy evidence",
            license_reference="internal",
        )
        rate = legacy.record_estimate_rate(
            price_source=source,
            actor=self.actor,
            resource_type="labor",
            code="L1",
            unit_of_measure=self.unit,
            rate=Decimal(7),
        )
        legacy.approve_estimate(estimate=self.estimate, actor=self.actor)
        before = {
            label: list(
                model.objects.order_by("pk").values(
                    *[
                        f.attname
                        for f in model._meta.concrete_fields
                        if f.name != "price_book_mapping"
                    ]
                )
            )
            for label, model in [
                ("items", m.EstimateItem),
                ("revisions", m.EstimateRevision),
                ("sources", m.EstimatePriceSource),
                ("rates", m.EstimateRate),
            ]
        }
        latest = ("estimates", "0006_cep035_price_book_version_mapping")
        previous = ("estimates", "0005_p4_s01_s06_estimate_depth")
        try:
            MigrationExecutor(connection).migrate([previous])
            self.assertNotIn(
                "estimates_pricebook", connection.introspection.table_names()
            )
            MigrationExecutor(connection).migrate([latest])
            for label, model in [
                ("items", m.EstimateItem),
                ("revisions", m.EstimateRevision),
                ("sources", m.EstimatePriceSource),
                ("rates", m.EstimateRate),
            ]:
                self.assertEqual(
                    list(
                        model.objects.order_by("pk").values(
                            *[
                                f.attname
                                for f in model._meta.concrete_fields
                                if f.name != "price_book_mapping"
                            ]
                        )
                    ),
                    before[label],
                )
            self.assertEqual(
                m.EstimateRate.objects.get(pk=rate.pk).source_version_snapshot, "1"
            )
            self.assertFalse(
                m.EstimateItem.objects.exclude(price_book_mapping=None).exists()
            )
            self.assertFalse(m.EstimatePriceBookMapping.objects.exists())
            if path := os.environ.get("CEP035_MIGRATION_TRACE_PATH"):
                Path(path).write_text(
                    json.dumps(
                        {
                            "populated_legacy_preservation": "PASS",
                            "before_after_equal": True,
                            "rows": {k: len(v) for k, v in before.items()},
                            "inferred_mappings": 0,
                            "unmapped_exception": "NO_AUTHORITATIVE_PRICE_BOOK_MAPPING",
                            "rollback_reapply": "PASS",
                        },
                        indent=2,
                    ),
                    encoding="utf-8",
                )
        finally:
            MigrationExecutor(connection).migrate([latest])


class PriceBookAffectedRegression(PriceBookFixture, TestCase):
    def setUp(self):
        super().setUp()
        self.owner = self.actor
        self.other = User.objects.create_user(username="cep035-other")
        self.other_organization = Organization.objects.create(
            name="Other", slug="cep035-other"
        )
        self.other_organization.memberships.create(
            user=self.other,
            role="company_owner",
            role_definition=self.role,
            status="active",
        )
        self.unit.code = "PB-EA"
        self.unit.symbol = "pb-ea"
        self.unit.save()

    test_revision_history = depth_tests.EstimateDepthTests.test_comparison_uses_revision_evidence_and_approved_assumption_is_immutable
    test_legacy_source_boundary = depth_tests.EstimateDepthTests.test_source_lineage_requires_same_tenant_and_external_source_is_closed
    test_import_preview = depth_tests.EstimateDepthTests.test_preview_rejects_formula_and_unknown_mapping_without_mutation
