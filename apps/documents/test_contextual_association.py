"""HTTP and transactional evidence for contextual association of five sources."""

from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.documents import test_related_documents as phase1
from apps.documents import tests as dms_fixture
from apps.documents.association import CHOICE_PAGE_SIZE, link_in_context
from apps.documents.models import Document, DocumentLink, DocumentVersion
from apps.documents.presentation import SOURCE_ROUTES, related_documents_for
from apps.documents.services import add_document_link
from apps.projects.models import Project, ProjectSite


class _Page(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.hidden = {}
        self.text = []
        self.document_form = False
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        data = dict(attrs)
        if tag == "form":
            self.document_form = data.get("aria-label") in {
                "بارگذاری سند جدید",
                "پیوند سند موجود",
            }
        if self.document_form and tag == "input" and data.get("type") == "hidden":
            self.hidden[data["name"]] = data.get("value", "")

    def handle_endtag(self, tag):
        if tag == "form":
            self.document_form = False

    def handle_data(self, data):
        self.text.append(data)


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class ContextualAssociationTests(TestCase):
    setUp = dms_fixture.DocumentServiceTests.setUp
    _pdf_upload = staticmethod(dms_fixture.DocumentServiceTests._pdf_upload)
    _create_document = dms_fixture.DocumentServiceTests._create_document
    targets = phase1.RelatedDocumentsTests.targets
    reader = phase1.RelatedDocumentsTests.reader
    clean_version = phase1.RelatedDocumentsTests.clean_version

    def login(self, user=None, client=None):
        client = client or self.client
        client.force_login(user or self.owner)
        session = client.session
        session["active_organization_id"] = str(self.organization.pk)
        session.save()
        return client

    def url(self, action, kind="project", target=None):
        return reverse(
            "documents:contextual-" + action,
            args=[kind, (target or self.project).pk],
        )

    def get_form(self, action, kind="project", target=None, client=None):
        response = (client or self.client).get(self.url(action, kind, target))
        self.assertEqual(response.status_code, 200)
        return response, _Page(response.content.decode()).hidden

    def upload_data(self, hidden, *, reference="CONTEXT-NEW"):
        return {
            **hidden,
            "document_type": "general",
            "title": "سند زمینه‌ای مرجع",
            "reference": reference,
            "description": "سند آزمون زمینه‌ای",
            "category": "",
            "confidentiality": "internal",
            "access_expires_at": "",
            "file": self._pdf_upload(),
        }

    def test_contextual_upload_for_all_five_sources(self):
        self.login()
        for index, (kind, target) in enumerate(
            zip(SOURCE_ROUTES, self.targets(), strict=True)
        ):
            with self.subTest(kind=kind):
                response, hidden = self.get_form("upload", kind, target)
                context = response.context["association_context"]
                self.assertEqual(hidden[kind], str(target.pk))
                self.assertEqual(
                    response.context["form"].fields[kind].widget.input_type, "hidden"
                )
                self.assertContains(response, context.project_title)
                self.assertContains(
                    response, f'href="{context.source.url.replace("&", "&amp;")}"'
                )
                visible = " ".join(_Page(response.content.decode()).text)
                self.assertNotIn(str(target.pk), visible)
                self.assertNotContains(
                    response, "id_contract" if kind != "contract" else "id_project"
                )
                before = (Document.objects.count(), DocumentLink.objects.count())
                cancelled = self.client.get(context.source.url)
                self.assertEqual(cancelled.status_code, 200)
                self.assertEqual(
                    (Document.objects.count(), DocumentLink.objects.count()), before
                )
                invalid = self.upload_data(hidden, reference=f"CONTEXT-UP-{index}")
                invalid["title"] = ""
                errors = self.client.post(self.url("upload", kind, target), invalid)
                self.assertEqual(errors.status_code, 400)
                self.assertContains(errors, context.source.title, status_code=400)
                self.assertContains(
                    errors, context.source.url.replace("&", "&amp;"), status_code=400
                )
                hidden = _Page(errors.content.decode()).hidden
                result = self.client.post(
                    self.url("upload", kind, target),
                    self.upload_data(hidden, reference=f"CONTEXT-UP-{index}"),
                )
                self.assertRedirects(
                    result, context.source.url, fetch_redirect_response=False
                )
                document = Document.objects.get(reference=f"CONTEXT-UP-{index}")
                self.assertEqual(document.links.count(), 1)
                self.assertEqual(document.links.get().target, target)
                self.assertEqual(document.versions.count(), 1)
                self.assertFalse(document.current_version.is_available)
                self.assertEqual(document.retention_classification, "standard_document")
                returned = self.client.get(context.source.url)
                self.assertContains(returned, document.title)
                self.assertEqual(
                    self.client.get(
                        reverse("documents:download", args=[document.pk])
                    ).status_code,
                    403,
                )

    def test_existing_document_for_all_five_sources_preserves_identity_versions(self):
        self.login()
        origin = Project.objects.create(
            organization=self.organization, code="ORIGIN", name="پروژه منبع"
        )
        document = self._create_document(target=origin)
        version_id = document.current_version_id
        for kind, target in zip(SOURCE_ROUTES, self.targets(), strict=True):
            with self.subTest(kind=kind):
                response, hidden = self.get_form("link", kind, target)
                context = response.context["association_context"]
                self.assertContains(response, document.title)
                self.assertContains(response, document.document_number)
                self.assertContains(response, "جست‌وجو با عنوان یا شماره سند")
                before = document.links.count()
                self.assertEqual(self.client.get(context.source.url).status_code, 200)
                self.assertEqual(document.links.count(), before)
                errors = self.client.post(
                    self.url("link", kind, target), {**hidden, "document": ""}
                )
                self.assertEqual(errors.status_code, 400)
                self.assertContains(errors, context.source.title, status_code=400)
                self.assertContains(
                    errors, context.source.url.replace("&", "&amp;"), status_code=400
                )
                hidden = _Page(errors.content.decode()).hidden
                result = self.client.post(
                    self.url("link", kind, target),
                    {**hidden, "document": str(document.pk)},
                )
                self.assertRedirects(
                    result, context.source.url, fetch_redirect_response=False
                )
                document.refresh_from_db()
                self.assertEqual(document.current_version_id, version_id)
                self.assertEqual(document.versions.count(), 1)
                self.assertEqual(Document.objects.count(), 1)
                self.assertEqual(document.links.filter(**{kind: target}).count(), 1)
        self.assertEqual(document.links.count(), 6)

    def test_duplicate_associations_and_retry_do_not_add_rows(self):
        self.login()
        origin = Project.objects.create(
            organization=self.organization, code="RETRY", name="Retry origin"
        )
        document = self._create_document(target=origin)
        _, hidden = self.get_form("link")
        data = {**hidden, "document": str(document.pk)}
        self.assertEqual(self.client.post(self.url("link"), data).status_code, 302)
        before = document.links.count()
        self.assertEqual(self.client.post(self.url("link"), data).status_code, 400)
        self.assertEqual(document.links.count(), before)
        self.assertEqual(document.versions.count(), 1)
        with self.assertRaises(ValidationError):
            link_in_context(
                user=self.owner,
                organization=self.organization,
                kind="project",
                identifier=self.project.pk,
                document_id=document.pk,
            )
        self.assertEqual(document.links.count(), before)

    def test_file_and_required_field_errors_keep_source_and_cancel(self):
        self.login()
        response, hidden = self.get_form("upload")
        source = response.context["association_context"].source
        data = self.upload_data(hidden)
        data["title"] = ""
        data["file"] = self._pdf_upload()
        result = self.client.post(self.url("upload"), data)
        self.assertEqual(result.status_code, 400)
        self.assertContains(result, self.project.name, status_code=400)
        self.assertContains(result, source.url, status_code=400)
        self.assertEqual(Document.objects.count(), 0)
        bad = self.upload_data(_Page(result.content.decode()).hidden)
        bad["file"] = self._pdf_upload()
        bad["file"].file.seek(0)
        bad["file"].file.truncate(0)
        bad["file"].file.write(b"not-a-pdf")
        bad["file"].file.seek(0)
        result = self.client.post(self.url("upload"), bad)
        self.assertEqual(result.status_code, 400)
        self.assertContains(
            result, "محتوای فایل بارگذاری‌شده معتبر نیست", status_code=400
        )
        self.assertEqual(Document.objects.count(), 0)

    def test_forged_target_token_and_additional_relationships_are_rejected(self):
        self.login()
        _, hidden = self.get_form("upload")
        other = Project.objects.create(
            organization=self.organization, code="OTHER", name="Other project"
        )
        for overrides, endpoint in (
            ({"project": str(other.pk)}, self.url("upload")),
            ({}, self.url("upload", target=other)),
            ({"project": str(other.pk)}, self.url("upload", target=other)),
            ({"contract": str(other.pk)}, self.url("upload")),
            ({"organization": str(self.other_organization.pk)}, self.url("upload")),
            ({"context_token": "forged"}, self.url("upload")),
            ({"next": "https://evil.example"}, self.url("upload")),
        ):
            with self.subTest(overrides=tuple(overrides)):
                result = self.client.post(
                    endpoint, {**self.upload_data(hidden), **overrides}
                )
                self.assertEqual(result.status_code, 400)
                self.assertEqual(Document.objects.count(), 0)

    def test_foreign_targets_and_unsafe_navigation_are_denied(self):
        self.login()
        foreign = Project.objects.create(
            organization=self.other_organization, code="FOREIGN", name="Foreign hidden"
        )
        for action in ("upload", "link", "choices"):
            self.assertEqual(
                self.client.get(self.url(action, target=foreign)).status_code, 403
            )
            self.assertEqual(
                self.client.get(
                    self.url(action), {"next": "//evil.example"}
                ).status_code,
                403,
            )
            self.assertEqual(
                self.client.get(
                    self.url(action), {"project": str(foreign.pk)}
                ).status_code,
                403,
            )
            self.assertEqual(
                self.client.get(self.url(action, kind="inspection")).status_code, 403
            )

    def test_picker_search_excludes_duplicates_and_foreign_documents(self):
        self.login()
        origin = Project.objects.create(
            organization=self.organization, code="FIND", name="Find origin"
        )
        document = self._create_document(target=origin, title="قابل جستجو سند مرجع")
        linked = self._create_document(
            target=self.project, title="Already linked", reference="LINKED"
        )
        foreign = self._create_document(
            organization=self.other_organization,
            actor=self.other_user,
            target=Project.objects.create(
                organization=self.other_organization, code="F", name="Foreign"
            ),
            reference="FOREIGN-DOC",
            title="Foreign hidden title",
        )
        result = self.client.get(self.url("choices"), {"q": document.document_number})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(
            [row["value"] for row in result.json()["results"]], [str(document.pk)]
        )
        label = result.json()["results"][0]["label"]
        for value in (document.title, document.document_number, "عمومی", "نسخه 1"):
            self.assertIn(value, label)
        self.assertNotIn(str(document.pk), label)
        result = self.client.get(self.url("choices"))
        self.assertNotIn(str(linked.pk), str(result.json()))
        self.assertNotIn(foreign.title, str(result.json()))
        self.assertIn("no-store", result["Cache-Control"])
        _, hidden = self.get_form("link")
        self.assertEqual(
            self.client.post(
                self.url("link"), {**hidden, "document": str(foreign.pk)}
            ).status_code,
            400,
        )

    def test_document_view_and_upload_permissions_are_separate_from_download(self):
        reader = self.reader(["projects.view", "documents.view", "documents.upload"])
        self.login(reader)
        _response, hidden = self.get_form("upload")
        result = self.client.post(self.url("upload"), self.upload_data(hidden))
        self.assertEqual(result.status_code, 302)
        document = Document.objects.get(reference="CONTEXT-NEW")
        self.clean_version(document.current_version)
        self.assertEqual(
            self.client.get(
                reverse("documents:download", args=[document.pk])
            ).status_code,
            403,
        )
        panel = related_documents_for(
            user=reader, organization=self.organization, target=self.project
        )
        self.assertTrue(panel.upload_url)
        self.assertTrue(panel.link_url)
        self.assertFalse(panel.rows[0].download_url)

    def test_viewer_has_no_contextual_mutation_actions_or_endpoints(self):
        reader = self.reader(["projects.view", "documents.view"])
        self.login(reader)
        panel = related_documents_for(
            user=reader, organization=self.organization, target=self.project
        )
        self.assertTrue(panel is None or not panel.upload_url)
        self.assertFalse(panel.link_url)
        for action in ("upload", "link", "choices"):
            self.assertEqual(self.client.get(self.url(action)).status_code, 403)

    def test_upload_only_persona_cannot_read_picker_or_contextual_forms(self):
        reader = self.reader(["projects.view", "documents.upload"])
        self.login(reader)
        for action in ("upload", "link", "choices"):
            self.assertEqual(self.client.get(self.url(action)).status_code, 403)

    def test_project_and_site_scope_are_rechecked(self):
        site = ProjectSite.objects.create(
            organization=self.organization,
            project=self.project,
            code="ONLY-SITE",
            name="Scoped site",
        )
        reader = self.reader(
            ["projects.view", "documents.view", "documents.upload"], site=site
        )
        self.login(reader)
        panel = related_documents_for(
            user=reader, organization=self.organization, target=self.project
        )
        self.assertTrue(panel is None or not panel.upload_url)
        for action in ("upload", "link", "choices"):
            self.assertEqual(self.client.get(self.url(action)).status_code, 403)

    def test_site_scoped_daily_report_upload_and_denied_other_site(self):
        report = self.targets()[-1]
        reader = self.reader(
            ["daily_reports.view", "documents.view", "documents.upload"],
            site=report.site,
        )
        self.login(reader)
        _, hidden = self.get_form("upload", "daily_report", report)
        result = self.client.post(
            self.url("upload", "daily_report", report), self.upload_data(hidden)
        )
        self.assertEqual(result.status_code, 302)
        document = Document.objects.get(reference="CONTEXT-NEW")
        self.assertEqual(document.links.get().daily_report, report)
        other_site = ProjectSite.objects.create(
            organization=self.organization,
            project=self.project,
            code="OTHER-SITE",
            name="Other site",
        )
        from apps.daily_reports.models import DailyReport

        denied = DailyReport.objects.create(
            organization=self.organization,
            project=self.project,
            site=other_site,
            reporting_date=report.reporting_date,
            work_performed="Other site report",
        )
        for action in ("upload", "link", "choices"):
            self.assertEqual(
                self.client.get(self.url(action, "daily_report", denied)).status_code,
                403,
            )

    def test_authority_is_rechecked_inside_upload_transaction(self):
        self.login()
        _, hidden = self.get_form("upload")
        from apps.documents.association import upload_in_context

        def revoke_then_upload(**kwargs):
            self.organization.memberships.filter(user=self.owner).update(
                status="suspended"
            )
            return upload_in_context(**kwargs)

        with patch(
            "apps.documents.contextual_views.upload_in_context",
            side_effect=revoke_then_upload,
        ):
            result = self.client.post(self.url("upload"), self.upload_data(hidden))
        self.assertEqual(result.status_code, 403)
        self.assertEqual(Document.objects.count(), 0)

    def test_all_context_document_permissions_and_metadata_are_filtered(self):
        targets = self.targets()
        denied = Project.objects.create(
            organization=self.organization, code="DENIED", name="Denied project"
        )
        document = self._create_document(title="All context secret")
        add_document_link(document=document, actor=self.owner, target=denied)
        reader = self.reader(
            ["projects.view", "contracts.view", "documents.view", "documents.upload"],
            project=self.project,
        )
        self.login(reader)
        endpoint = self.url("choices", "contract", targets[1])
        self.assertEqual(self.client.get(endpoint).json()["results"], [])
        _, hidden = self.get_form("link", "contract", targets[1])
        result = self.client.post(
            self.url("link", "contract", targets[1]),
            {**hidden, "document": str(document.pk)},
        )
        self.assertEqual(result.status_code, 400)
        self.assertNotContains(result, document.title, status_code=400)
        self.assertFalse(document.links.filter(contract=targets[1]).exists())

    def test_stale_compatibility_mapping_cannot_be_selected(self):
        self.login()
        contract = self.targets()[1]
        document = self._create_document(title="Hidden stale mapping")
        extra = Project.objects.create(
            organization=self.organization, code="MISMATCH", name="Mismatch"
        )
        DocumentLink.objects.create(
            organization=self.organization, document=document, project=extra
        )
        self.assertEqual(
            self.client.get(self.url("choices", "contract", contract)).json()[
                "results"
            ],
            [],
        )
        _, hidden = self.get_form("link", "contract", contract)
        result = self.client.post(
            self.url("link", "contract", contract),
            {**hidden, "document": str(document.pk)},
        )
        self.assertEqual(result.status_code, 400)
        self.assertNotContains(result, document.title, status_code=400)

    def test_link_rollback_preserves_typed_legacy_atomicity(self):
        self.login()
        contract = self.targets()[1]
        document = self._create_document()
        _, hidden = self.get_form("link", "contract", contract)
        with patch(
            "apps.documents.services.create_typed_link",
            side_effect=ValidationError("INTERNAL_MODEL_ERROR"),
        ):
            result = self.client.post(
                self.url("link", "contract", contract),
                {**hidden, "document": str(document.pk)},
            )
        self.assertEqual(result.status_code, 400)
        self.assertFalse(document.links.filter(contract=contract).exists())
        self.assertEqual(document.links.count(), 1)
        self.assertEqual(document.versions.count(), 1)
        self.assertNotContains(result, "INTERNAL_MODEL_ERROR", status_code=400)

    def test_upload_rollback_removes_only_the_new_binary(self):
        self.login()
        _, hidden = self.get_form("upload")

        def files():
            return {
                p for p in Path(self.media_directory.name).rglob("*") if p.is_file()
            }

        before = files()
        with patch(
            "apps.documents.services.record_audit_event",
            side_effect=ValidationError("INTERNAL_ERROR"),
        ):
            result = self.client.post(self.url("upload"), self.upload_data(hidden))
        self.assertEqual(result.status_code, 400)
        self.assertEqual(Document.objects.count(), 0)
        self.assertEqual(DocumentVersion.objects.count(), 0)
        self.assertEqual(files(), before)
        self.assertNotContains(result, "INTERNAL_ERROR", status_code=400)

    def test_expired_context_keeps_source_and_refreshes_form_intent(self):
        self.login()
        with patch(
            "django.core.signing.time.time",
            return_value=timezone.now().timestamp() - 7200,
        ):
            _, hidden = self.get_form("upload")
        result = self.client.post(self.url("upload"), self.upload_data(hidden))
        self.assertEqual(result.status_code, 400)
        self.assertContains(result, self.project.name, status_code=400)
        refreshed = _Page(result.content.decode()).hidden
        self.assertNotEqual(refreshed["context_token"], hidden["context_token"])
        result = self.client.post(self.url("upload"), self.upload_data(refreshed))
        self.assertEqual(result.status_code, 302)

    def test_csrf_is_required_for_both_actions(self):
        client = self.login(client=Client(enforce_csrf_checks=True))
        for action in ("upload", "link"):
            self.assertEqual(client.post(self.url(action), {}).status_code, 403)
        _, hidden = self.get_form("upload", client=client)
        result = client.post(self.url("upload"), self.upload_data(hidden))
        self.assertEqual(result.status_code, 302)

    def test_archived_expired_and_sealed_documents_never_enter_picker(self):
        self.login()
        contract = self.targets()[1]
        for index, (field, value) in enumerate(
            (
                ("archived_at", timezone.now()),
                ("access_expires_at", timezone.now()),
                ("retention_classification", "sealed_supplier_quote_evidence"),
            )
        ):
            document = self._create_document(reference=f"EXCLUDE-{index}")
            setattr(document, field, value)
            document.save()
        self.assertEqual(
            self.client.get(self.url("choices", "contract", contract)).json()[
                "results"
            ],
            [],
        )

    def test_candidate_pages_search_and_selected_value_retention(self):
        self.login()
        contract = self.targets()[1]
        for index in range(CHOICE_PAGE_SIZE + 1):
            document = self._create_document(
                reference=f"PAGE-{index}", title=f"Document {index:02}"
            )
        endpoint = self.url("choices", "contract", contract)
        first = self.client.get(endpoint).json()
        self.assertEqual(len(first["results"]), CHOICE_PAGE_SIZE)
        self.assertTrue(first["next"])
        second = self.client.get(first["next"]).json()
        self.assertEqual(len(second["results"]), 1)
        self.assertIsNone(second["next"])
        found = self.client.get(
            endpoint, {"q": f"Document {CHOICE_PAGE_SIZE:02}"}
        ).json()["results"]
        self.assertEqual([row["value"] for row in found], [str(document.pk)])
        _, hidden = self.get_form("link", "contract", contract)
        result = self.client.post(
            self.url("link", "contract", contract),
            {
                **hidden,
                "document": str(document.pk),
                "context_token": "expired",
            },
        )
        self.assertEqual(result.status_code, 400)
        self.assertContains(result, "selected", status_code=400)
        self.assertContains(result, document.title, status_code=400)
