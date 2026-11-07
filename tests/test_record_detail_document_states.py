"""Record Detail follow-up: actual DMS states, versions and source navigation."""

from pathlib import Path

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.urls import reverse
from test_daily_report_references import DailyReferenceFixture

from apps.accounts.models import User
from apps.billing import test_mvp03_browser as browser_fixture
from apps.daily_reports.references import create_report_with_references
from apps.documents.models import DocumentProcessingVerdict
from apps.documents.services import (
    add_document_version,
    create_document,
    record_document_processing_assessment,
)
from apps.organizations.access_services import assign_platform_role
from apps.organizations.models import BusinessPermission, PlatformRoleCode


@override_settings(
    PRODUCT_SURFACE_PROFILE="MVP",
    PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
)
class RecordDetailDocumentStatesTests(DailyReferenceFixture, StaticLiveServerTestCase):
    browser = browser_fixture.ContractBillingBrowserTests.browser
    _fixture_teardown = browser_fixture.ContractBillingBrowserTests._fixture_teardown
    browser_evidence_directory = Path("output/detail-page-rollout/follow-up")

    def setup_documents(self):
        self.setup_daily()
        assigner = User.objects.create_superuser(username="detail-role-assigner")
        approver = User.objects.create_superuser(username="detail-role-approver")
        self.operator = User.objects.create_user(username="detail-scan-operator")
        assign_platform_role(
            actor=assigner,
            approver=approver,
            target=self.operator,
            role=PlatformRoleCode.PLATFORM_OPERATIONS,
            reason="Synthetic Detail browser scan evidence only",
        )

    def assess(self, version, verdict):
        record_document_processing_assessment(
            version=version,
            actor=self.operator,
            verdict=verdict,
            adapter_code="detail-test-fixture",
        )

    def scenarios(self, name, path, **extra):
        return [
            {
                "name": f"{name}-{width}",
                "path": path,
                "width": width,
                "status": 200,
                "screenshot": True,
                "viewportScreenshot": True,
                "fullPageScreenshot": True,
                "bottomScreenshot": True,
                "noJsErrors": True,
                **extra,
            }
            for width in (1440, 1024, 390)
        ]

    def test_availability_and_immutable_versions(self):
        self.setup_documents()
        path = reverse("documents:detail", args=[self.document.pk])
        current_download = reverse("documents:download", args=[self.document.pk])
        first = self.document.current_version
        first_download = reverse(
            "documents:version-download", args=[self.document.pk, first.pk]
        )
        self.browser(
            self.owner,
            self.scenarios(
                "document-unassessed",
                path,
                absentLinks=[current_download, first_download],
            ),
        )
        self.assertEqual(self.client.get(current_download).status_code, 403)
        self.assess(first, DocumentProcessingVerdict.CLEAN)
        self.browser(
            self.owner,
            self.scenarios(
                "document-clean", path, mustLinks=[current_download, first_download]
            ),
        )
        response = self.client.get(first_download)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response["Content-Disposition"].startswith("attachment;"))
        response.close()
        self.assess(first, DocumentProcessingVerdict.UNSAFE)
        self.browser(
            self.owner,
            self.scenarios(
                "document-unsafe", path, absentLinks=[current_download, first_download]
            ),
        )
        self.assertEqual(self.client.get(first_download).status_code, 403)
        self.assess(first, DocumentProcessingVerdict.CLEAN)
        second = add_document_version(
            document=self.document, actor=self.owner, upload=self.pdf()
        )
        second_download = reverse(
            "documents:version-download", args=[self.document.pk, second.pk]
        )
        self.browser(
            self.owner,
            self.scenarios(
                "document-new-version-quarantined",
                path,
                mustLinks=[first_download],
                absentLinks=[current_download, second_download],
            ),
        )
        self.assertEqual(self.client.get(second_download).status_code, 403)
        self.assess(second, DocumentProcessingVerdict.CLEAN)
        self.browser(
            self.owner,
            self.scenarios(
                "document-two-clean-versions",
                path,
                mustLinks=[current_download, first_download, second_download],
            ),
        )
        self.document.refresh_from_db()
        self.assertEqual(self.document.current_version_id, second.pk)
        self.assertEqual(self.document.versions.count(), 2)
        role = self.reader_scope.membership.role_definition
        role.permissions.add(
            *BusinessPermission.objects.filter(
                code__in=["documents.view", "projects.view"]
            )
        )
        self.browser(
            self.reader,
            self.scenarios(
                "document-no-download-permission",
                path,
                absentLinks=[current_download, first_download, second_download],
                steps=[
                    {
                        "inspect": "document.querySelectorAll('main form').length === 0",
                        "description": "document read authority does not expose write forms",
                    }
                ],
            ),
        )
        self.assertEqual(self.client.get(current_download).status_code, 403)

    def test_related_documents_expansion_and_source_return(self):
        self.setup_daily()
        report = create_report_with_references(
            actor=self.owner,
            organization=self.organization,
            report_values=self.report_values(),
            document_ids=[self.document.pk],
        )
        for index in range(6):
            document = create_document(
                organization=self.organization,
                actor=self.owner,
                target=report,
                document_type="general",
                title=("نقشه اجرایی و مستندات کنترل کیفیت کارگاه " * 5).strip()
                if index == 0
                else f"سند مرتبط شماره {index + 1} برای گزارش روزانه",
                upload=self.pdf(),
            )
            if index == 0:
                long_title_document = document
        path = reverse("daily_reports:detail", args=[report.pk])
        self.browser(
            self.owner,
            self.scenarios(
                "related-documents-expanded",
                path,
                steps=[
                    {
                        "toggleSelector": ".erp-related-documents-more > summary",
                        "inspect": "document.querySelectorAll('#related-documents .erp-related-documents-row').length === 7 && document.querySelector('.erp-related-documents-more').open",
                        "description": "all seven authorized related documents are accessible",
                    },
                    {
                        "clickSelector": "#related-documents .erp-related-documents-name a",
                        "afterPrefix": "/documents/",
                    },
                    {
                        "inspect": "location.search.includes('related_to=daily_report') && document.querySelector('main .erp-document-return').getAttribute('href').endsWith('#related-documents')",
                        "description": "source context uses the real authorized source link",
                    },
                    {"clickSelector": "main .erp-document-return", "afterPath": path},
                    {
                        "inspect": "location.hash === '#related-documents'",
                        "description": "return lands at the source related-document section",
                    },
                    {"history": "back", "afterPrefix": "/documents/"},
                    {"history": "forward", "afterPath": path},
                    {"reload": True, "afterPath": path},
                    {
                        "toggleSelector": ".erp-related-documents-more > summary",
                        "inspect": "document.querySelector('.erp-related-documents-more').open",
                        "description": "expanded authorized records are retained in the final screenshot",
                    },
                ],
            ),
        )
        source_path = reverse("documents:detail", args=[long_title_document.pk])
        source_path += f"?related_to=daily_report&related_id={report.pk}"
        self.browser(
            self.owner,
            self.scenarios(
                "document-source-return-context",
                source_path,
                steps=[
                    {
                        "inspect": "!!document.querySelector('.erp-document-return') && document.querySelectorAll('header [data-context-project]').length === 1",
                        "description": "long record identity and source return coexist with one global context selector",
                    }
                ],
            ),
        )

    def test_invalid_version_keeps_detail_layout_and_labels(self):
        self.setup_daily()
        path = reverse("documents:detail", args=[self.document.pk])
        action = reverse("documents:version-add", args=[self.document.pk])
        self.browser(
            self.owner,
            self.scenarios(
                "document-version-validation",
                path,
                status=400,
                steps=[
                    {
                        "inspect": "document.querySelector('main form[enctype]').noValidate = true",
                        "description": "exercise existing server validation",
                    },
                    {
                        "submit": True,
                        "formSelector": "main form[enctype]",
                        "afterPath": action,
                    },
                    {
                        "inspect": "document.querySelectorAll('main h1').length === 1 && document.querySelector('#id_file').getAttribute('aria-invalid') === 'true' && document.querySelector('#id_file-errors') && document.querySelector('label[for=\"id_file\"]')",
                        "description": "server file errors remain labeled inside the same Detail pattern",
                    },
                ],
            ),
        )
        self.assertEqual(self.document.versions.count(), 1)
