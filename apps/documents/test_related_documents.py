"""Read projections must preserve the existing DMS and source boundaries."""

from datetime import date, timedelta
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlsplit

from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.audit.models import AuditEvent
from apps.contracts.models import Contract
from apps.daily_reports.models import DailyReport
from apps.documents import tests as dms_fixture
from apps.documents.models import DocumentLink, DocumentProcessingAssessment
from apps.documents.presentation import (
    document_return_source,
    document_sources_for,
    related_documents_for,
)
from apps.documents.services import add_document_link, add_document_version
from apps.estimates.services import create_estimate
from apps.expenses.models import Expense
from apps.organizations.models import (
    BusinessPermission,
    MembershipRoleAssignment,
    MembershipScopeGrant,
    OrganizationMembership,
    OrganizationRole,
)
from apps.projects.models import Project, ProjectSite


class _RelatedSectionParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.depth = 0
        self.controls = []

    def handle_starttag(self, tag, attrs):
        if tag == "section" and (
            self.depth or dict(attrs).get("id") == "related-documents"
        ):
            self.depth += 1
        if self.depth and tag in {"form", "input", "button"}:
            self.controls.append(tag)

    def handle_endtag(self, tag):
        if tag == "section" and self.depth:
            self.depth -= 1


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class RelatedDocumentsTests(TestCase):
    setUp = dms_fixture.DocumentServiceTests.setUp
    _pdf_upload = staticmethod(dms_fixture.DocumentServiceTests._pdf_upload)
    _create_document = dms_fixture.DocumentServiceTests._create_document

    def panel(self, target=None, user=None):
        return related_documents_for(
            user=user or self.owner,
            organization=self.organization,
            target=target or self.project,
        )

    def reader(self, permissions, *, project=None, site=None):
        from apps.accounts.models import User

        user = User.objects.create_user(username="related-documents-reader")
        role = OrganizationRole.objects.create(
            organization=self.organization, code="related-reader", name="Reader"
        )
        role.permissions.set(BusinessPermission.objects.filter(code__in=permissions))
        membership = OrganizationMembership.objects.create(
            organization=self.organization,
            user=user,
            status="active",
            role_definition=role,
        )
        MembershipRoleAssignment.objects.create(
            organization=self.organization,
            membership=membership,
            role=role,
            reason="Explicit isolated read-projection test",
        )
        MembershipScopeGrant.objects.create(
            organization=self.organization,
            membership=membership,
            scope_type="site" if site else "project" if project else "organization",
            project=site.project if site else project,
            site=site,
            reason="Explicit isolated read-projection scope",
        )
        return user

    def sources(self, document, user=None):
        return document_sources_for(
            user=user or self.owner,
            organization=self.organization,
            document=document,
        )

    def clean_version(self, version):
        return DocumentProcessingAssessment.objects.create(
            organization=self.organization,
            version=version,
            sequence=1,
            verdict="clean",
            input_sha256=version.sha256,
            adapter_code="isolated-fixture",
            recorded_by=self.owner,
        )

    def targets(self):
        contract = Contract.objects.create(
            organization=self.organization,
            project=self.project,
            contract_number="RELATED-C",
            title="قرارداد مرجع",
            counterparty_name="طرف نمونه",
            direction="receivable",
        )
        estimate = create_estimate(
            organization=self.organization,
            actor=self.owner,
            project=self.project,
            contract=contract,
            estimate_number="RELATED-E",
            title="برآورد مرجع",
        )
        expense = Expense.objects.create(
            organization=self.organization,
            project=self.project,
            description="هزینه مرجع",
            incurred_on=date(2026, 11, 1),
            amount="100",
        )
        site = ProjectSite.objects.create(
            organization=self.organization,
            project=self.project,
            code="RELATED-S",
            name="کارگاه مرجع",
        )
        report = DailyReport.objects.create(
            organization=self.organization,
            project=self.project,
            site=site,
            reporting_date=date(2026, 11, 1),
            work_performed="فعالیت مرجع",
        )
        return [self.project, contract, estimate, expense, report]

    def test_five_sources_deduplicate_mirrors_and_generate_safe_roundtrips(self):
        for index, target in enumerate(self.targets()):
            with self.subTest(source=type(target).__name__):
                document = self._create_document(
                    target=target, reference=f"RELATED-{index}"
                )
                panel = self.panel(target)
                self.assertEqual(panel.count, 1)
                self.assertEqual(panel.rows[0].version_number, 1)
                self.assertFalse(panel.rows[0].available)
                self.assertFalse(panel.rows[0].download_url)
                source = self.sources(document)[0]
                query = parse_qs(urlsplit(panel.rows[0].detail_url).query)
                request = RequestFactory().get(
                    "/documents/", {key: values[0] for key, values in query.items()}
                )
                self.assertEqual(document_return_source(request, (source,)), source)
                self.assertTrue(source.url.endswith("#related-documents"))
                self.assertFalse(source.url.startswith("//"))

    def test_only_direct_entity_links_are_projected(self):
        contract = self.targets()[1]
        self._create_document(target=contract)
        self.assertEqual(self.panel().count, 0)
        self.assertEqual(self.panel(contract).count, 1)

    def test_denied_dms_permission_hides_panel_and_count(self):
        self._create_document()
        reader = self.reader(["projects.view"])
        self.assertIsNone(self.panel(user=reader))
        html = render_to_string(
            "components/related_documents.html",
            {"related_documents": self.panel(user=reader), "source_label": "پروژه"},
        )
        self.assertNotIn("related-documents-heading", html)

    def test_missing_source_permission_and_foreign_target_fail_closed(self):
        reader = self.reader(["documents.view"])
        self.assertIsNone(self.panel(user=reader))
        foreign = Project.objects.create(
            organization=self.other_organization, code="RELATED-X", name="Foreign"
        )
        self.assertIsNone(self.panel(foreign))

    def test_all_linked_contexts_must_be_authorized(self):
        document = self._create_document()
        denied = Project.objects.create(
            organization=self.organization, code="RELATED-DENIED", name="Denied"
        )
        add_document_link(document=document, actor=self.owner, target=denied)
        reader = self.reader(["projects.view", "documents.view"], project=self.project)
        self.assertEqual(self.panel(user=reader).count, 0)
        self.assertEqual(self.panel().count, 1)

    def test_missing_compatibility_parity_hides_document(self):
        document = self._create_document()
        other = Project.objects.create(
            organization=self.organization, code="PARITY-X", name="Other source"
        )
        # A candidate still has a valid typed link, but an extra unmatched
        # compatibility row must make the detail-equivalent projection deny it.
        DocumentLink.objects.create(
            organization=self.organization, document=document, project=other
        )
        self.assertEqual(self.panel().count, 0)

    def test_daily_report_site_scope_does_not_expand_to_another_site(self):
        report = self.targets()[-1]
        self._create_document(target=report)
        other_site = ProjectSite.objects.create(
            organization=self.organization,
            project=self.project,
            code="OTHER-SITE",
            name="Other site",
        )
        denied = DailyReport.objects.create(
            organization=self.organization,
            project=self.project,
            site=other_site,
            reporting_date=date(2026, 11, 1),
            work_performed="Other site activity",
        )
        self._create_document(target=denied, reference="DENIED-SITE")
        reader = self.reader(["daily_reports.view", "documents.view"], site=report.site)
        self.assertEqual(self.panel(report, user=reader).count, 1)
        self.assertIsNone(self.panel(denied, user=reader))

    def test_archived_expired_sealed_and_deleted_source_documents_are_absent(self):
        document = self._create_document()
        for field, value in (
            ("archived_at", timezone.now()),
            ("access_expires_at", timezone.now() - timedelta(seconds=1)),
            ("retention_classification", "sealed_supplier_quote_evidence"),
        ):
            original = getattr(document, field)
            setattr(document, field, value)
            document.save()
            self.assertEqual(self.panel().count, 0)
            setattr(document, field, original)
            document.save()
        self.project.deleted_at = timezone.now()
        self.project.save()
        self.assertIsNone(self.panel())

    def test_download_requires_its_own_permission_and_exact_clean_version(self):
        document = self._create_document()
        self.clean_version(document.current_version)
        owner_row = self.panel().rows[0]
        self.assertTrue(owner_row.available)
        self.assertIn(str(document.current_version_id), owner_row.download_url)
        reader = self.reader(["projects.view", "documents.view"])
        self.assertTrue(self.panel(user=reader).rows[0].available)
        self.assertFalse(self.panel(user=reader).rows[0].download_url)
        add_document_version(
            document=document, actor=self.owner, upload=self._pdf_upload("new.pdf")
        )
        row = self.panel().rows[0]
        self.assertEqual(row.version_number, 2)
        self.assertFalse(row.available)
        self.assertFalse(row.download_url)

    def test_read_projection_does_not_record_a_download_or_change_links(self):
        document = self._create_document()
        self.clean_version(document.current_version)
        before = (AuditEvent.objects.count(), DocumentLink.objects.count())
        self.assertTrue(self.panel().rows[0].download_url)
        self.assertEqual(len(self.sources(document)), 1)
        self.assertEqual(
            (AuditEvent.objects.count(), DocumentLink.objects.count()), before
        )
        document.refresh_from_db()
        self.assertEqual(document.current_version.version_number, 1)

    def test_forged_return_context_never_produces_a_url(self):
        document = self._create_document()
        sources = self.sources(document)
        for query in (
            {"related_to": "project", "related_id": "https://evil.example"},
            {"related_to": "treasury_movement", "related_id": str(self.project.pk)},
            {"related_to": "project", "related_id": str(self.other_organization.pk)},
            {"next": "//evil.example"},
        ):
            self.assertIsNone(
                document_return_source(
                    RequestFactory().get("/documents/", query), sources
                )
            )

    def test_estimate_return_does_not_require_unauthorized_project_context(self):
        estimate = self.targets()[2]
        document = self._create_document(target=estimate)
        reader = self.reader(["estimates.view", "documents.view"])
        source = self.sources(document, user=reader)[0]
        self.assertNotIn("project_id=", source.url)

    def test_business_templates_have_one_navigation_and_one_read_only_section(self):
        self.client.force_login(self.owner)
        session = self.client.session
        session["active_organization_id"] = str(self.organization.pk)
        session.save()
        routes = [
            "projects:detail",
            "contracts:detail",
            "estimates:detail",
            "expenses:detail",
            "daily_reports:detail",
        ]
        for route, target in zip(routes, self.targets(), strict=True):
            with self.subTest(route=route):
                response = self.client.get(reverse(route, args=[target.pk]))
                self.assertEqual(response.status_code, 200)
                html = response.content.decode()
                self.assertEqual(html.count("data-related-documents-nav"), 1)
                self.assertEqual(html.count('id="related-documents"'), 1)
                self.assertContains(response, "سند مرتبط قابل مشاهده‌ای")
                self.assertNotIn("اسناد و گالری", html)
                # New section is read-only even on existing mutable business pages.
                parser = _RelatedSectionParser()
                parser.feed(html)
                self.assertFalse(parser.controls)

    def test_document_detail_shows_real_source_return_without_new_mutation_flows(self):
        document = self._create_document()
        self.client.force_login(self.owner)
        session = self.client.session
        session["active_organization_id"] = str(self.organization.pk)
        session.save()
        response = self.client.get(
            reverse("documents:detail", args=[document.pk]),
            {"related_to": "project", "related_id": str(self.project.pk)},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "بازگشت به اسناد مرتبط پروژه")
        self.assertContains(
            response,
            reverse("projects:detail", args=[self.project.pk]) + "#related-documents",
        )
