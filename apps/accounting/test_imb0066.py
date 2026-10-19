"""IMB-0066: bounded reads preserve Accounting's existing tenant authority."""

from datetime import date
from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.accounting import tests as accounting_tests
from apps.accounting.models import JournalEntry, JournalKind, JournalLine
from apps.audit.models import AuditEvent
from apps.organizations.models import MembershipRole, MembershipStatus


class JournalListBoundingTests(TestCase):
    setUp = accounting_tests.AccountingFoundationTests.setUp
    _member = accounting_tests.AccountingFoundationTests._member
    _activate_client = accounting_tests.AccountingTenantUiTests._activate_client

    def _journals(self, count: int) -> list[JournalEntry]:
        timestamp = timezone.now()
        with patch("django.utils.timezone.now", return_value=timestamp):
            return JournalEntry.objects.bulk_create(
                [
                    JournalEntry(
                        organization=self.organization,
                        period=self.period,
                        prepared_by=self.owner_membership,
                        kind=JournalKind.MANUAL,
                        document_date=date(2026, 1, 1),
                        accounting_date=date(2026, 1, 1),
                        created_at=timestamp,
                        description=f"bounded-journal-{index}",
                        source_key=f"bounded-{index}",
                    )
                    for index in range(count)
                ]
            )

    def test_pages_are_bounded_stable_disjoint_and_complete(self) -> None:
        journals = self._journals(61)
        self._activate_client(self.owner)
        expected = [j.pk for j in sorted(journals, key=lambda j: j.pk, reverse=True)]
        seen = []
        for number, size in ((1, 25), (2, 25), (3, 11)):
            response = self.client.get(
                reverse("accounting:journal_list"),
                {"page": number, "per_page": 100000, "sort": "organization"},
            )
            self.assertEqual(response.status_code, 200)
            page = response.context["page_obj"]
            self.assertEqual(len(page.object_list), size)
            self.assertEqual(page.paginator.count, 61)
            seen.extend(j.pk for j in response.context["journals"])
            self.assertContains(response, 'aria-label="صفحه‌بندی"')
        self.assertEqual(seen, expected)
        repeat = self.client.get(reverse("accounting:journal_list"), {"page": 2})
        self.assertEqual([j.pk for j in repeat.context["journals"]], expected[25:50])

    def test_queries_limit_journals_and_first_debit_without_line_prefetch(self) -> None:
        journals = self._journals(61)
        JournalLine.objects.bulk_create(
            [
                JournalLine(
                    organization=self.organization,
                    journal=journal,
                    account=self.debit_account,
                    line_number=number,
                    debit=Decimal(number),
                    source_line_uuid=uuid4(),
                )
                for journal in journals
                for number in range(1, 31)
            ]
        )
        self._activate_client(self.owner)
        before = (
            JournalEntry.objects.count(),
            JournalLine.objects.count(),
            AuditEvent.objects.count(),
        )
        with CaptureQueriesContext(connection) as captured:
            response = self.client.get(reverse("accounting:journal_list"), {"page": 2})
        selects = [
            q["sql"] for q in captured if 'FROM "accounting_journalentry"' in q["sql"]
        ]
        self.assertEqual(len(selects), 2)  # count plus one bounded source read
        self.assertTrue(any("LIMIT 25 OFFSET 25" in sql for sql in selects))
        self.assertTrue(any("LIMIT 1" in sql for sql in selects))
        self.assertFalse(
            any(
                'FROM "accounting_journalline"' in q["sql"]
                and 'FROM "accounting_journalentry"' not in q["sql"]
                for q in captured
            )
        )
        self.assertTrue(
            all(j.list_debit == Decimal(1) for j in response.context["journals"])
        )
        self.assertEqual(
            before,
            (
                JournalEntry.objects.count(),
                JournalLine.objects.count(),
                AuditEvent.objects.count(),
            ),
        )
        self.assertFalse(
            any(
                q["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))
                for q in captured
            )
        )

    def test_invalid_pages_and_empty_results_remain_bounded(self) -> None:
        self._activate_client(self.owner)
        empty = self.client.get(reverse("accounting:journal_list"), {"page": "bad"})
        self.assertEqual(empty.context["journals"], [])
        self._journals(26)
        for value, expected in (("bad", 1), ("0", 2), ("-1", 2), ("999999999999", 2)):
            response = self.client.get(
                reverse("accounting:journal_list"), {"page": value}
            )
            self.assertEqual(response.context["page_obj"].number, expected)
            self.assertLessEqual(len(response.context["journals"]), 25)

    def test_active_tenant_scope_and_detail_links_are_preserved(self) -> None:
        journal = self._journals(1)[0]
        self._activate_client(self.owner)
        response = self.client.get(
            reverse("accounting:journal_list"),
            {"organization": str(self.other_organization.pk)},
        )
        self.assertEqual([j.pk for j in response.context["journals"]], [journal.pk])
        self.assertContains(
            response, reverse("accounting:journal_detail", args=[journal.pk])
        )
        self._activate_client(self.other_owner, self.other_organization)
        response = self.client.get(
            reverse("accounting:journal_list"),
            {"organization": str(self.organization.pk)},
        )
        self.assertEqual(response.context["journals"], [])
        self.assertEqual(
            self.client.get(
                reverse("accounting:journal_detail", args=[journal.pk])
            ).status_code,
            404,
        )

    def test_missing_permission_and_inactive_membership_fail_closed(self) -> None:
        viewer = self._member("bounding-viewer", MembershipRole.VIEWER)
        # Viewer legitimately includes accounting.view; revoke its explicit role.
        self.organization.memberships.get(user=viewer).role_assignments.update(
            revoked_at=timezone.now()
        )
        self._activate_client(viewer)
        self.assertEqual(
            self.client.get(
                reverse("accounting:journal_list"), {"page": 2}
            ).status_code,
            403,
        )
        self.owner_membership.status = MembershipStatus.REVOKED
        self.owner_membership.save(update_fields=["status"])
        self._activate_client(self.owner)
        self.assertEqual(
            self.client.get(reverse("accounting:journal_list")).status_code, 403
        )

    def test_inactive_tenant_and_anonymous_requests_fail_closed(self) -> None:
        self._activate_client(self.owner)
        self.organization.status = "suspended"
        self.organization.save(update_fields=["status", "updated_at"])
        self.assertEqual(
            self.client.get(reverse("accounting:journal_list")).status_code, 403
        )
        self.client.logout()
        self.assertEqual(
            self.client.get(reverse("accounting:journal_list")).status_code, 302
        )

    def test_permission_without_organization_scope_is_denied(self) -> None:
        self._activate_client(self.approver)
        self.assertEqual(
            self.client.get(reverse("accounting:journal_list")).status_code, 200
        )
        self.organization.memberships.get(
            user=self.approver
        ).scope_grants.all().delete()
        self.assertEqual(
            self.client.get(reverse("accounting:journal_list")).status_code, 403
        )
