"""Exact-version presentation and source-owned registration security regressions."""

from datetime import date, timedelta
from decimal import Decimal
from html.parser import HTMLParser
from unittest.mock import patch
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.billing import test_commercial_controls as commercial_fixture
from apps.billing.commercial_services import (
    create_compliance_evidence,
    create_guarantee,
    create_retention_release,
)
from apps.contracts.contractual_services import (
    create_contractual_record,
    submit_contractual_record,
)
from apps.contracts.services import (
    add_contract_item,
    approve_contract_term_version,
    create_contract,
    create_contract_term_version,
    transition_contract_status,
)
from apps.daily_reports.field_services import (
    create_field_observation,
    submit_field_observation,
)
from apps.documents import test_related_documents as phase1
from apps.documents import tests as dms_fixture
from apps.documents.evidence import evidence_panel
from apps.documents.models import Document
from apps.documents.services import add_document_link, add_document_version
from apps.materials.models import Material, UnitOfMeasure
from apps.organizations.models import BusinessPermission
from apps.parties.services import create_business_party
from apps.projects.models import Project, ProjectSite
from apps.quality.services import create_quality_issue
from apps.safety.services import create_safety_incident


class Page(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.hidden = {}
        self.visible = []
        self.form = False
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "form":
            self.form = attrs.get("aria-label") == "انتخاب نسخه شاهد"
        if self.form and tag == "input" and attrs.get("type") == "hidden":
            self.hidden[attrs["name"]] = attrs.get("value", "")

    def handle_endtag(self, tag):
        if tag == "form":
            self.form = False

    def handle_data(self, data):
        self.visible.append(data)


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class EvidenceIntegrationTests(TestCase):
    setUp = dms_fixture.DocumentServiceTests.setUp
    _pdf_upload = staticmethod(dms_fixture.DocumentServiceTests._pdf_upload)
    _create_document = dms_fixture.DocumentServiceTests._create_document
    reader = phase1.RelatedDocumentsTests.reader
    clean_version = phase1.RelatedDocumentsTests.clean_version

    def login(self, user=None, client=None):
        client = client or self.client
        client.force_login(user or self.owner)
        session = client.session
        session["active_organization_id"] = str(self.organization.pk)
        session.save()
        return client

    def safety(self):
        return create_safety_incident(
            organization=self.organization,
            actor=self.owner,
            project=self.project,
            incident_number="PH3-S",
            occurred_at=timezone.now(),
            incident_type="near_miss",
            severity="high",
            description="رویداد ایمنی آزمایشی",
        )

    def quality(self):
        return create_quality_issue(
            organization=self.organization,
            actor=self.owner,
            project=self.project,
            issue_number="PH3-Q",
            identified_at=timezone.now(),
            issue_type="nonconformance",
            severity="major",
            description="مسئله کیفیت آزمایشی",
        )

    def observation(self):
        site = ProjectSite.objects.create(
            organization=self.organization,
            project=self.project,
            code="PH3-SITE",
            name="کارگاه آزمون",
        )
        return create_field_observation(
            organization=self.organization,
            actor=self.owner,
            project=self.project,
            site=site,
            kind="general",
            title="مشاهده آزمایشی",
            operation_key=uuid4(),
        )

    def material(self):
        unit = UnitOfMeasure.objects.create(
            organization=self.organization,
            code="PH3-UNIT",
            name="عدد",
            symbol="pcs",
            category="count",
        )
        return Material.objects.create(
            organization=self.organization,
            code="PH3-MAT",
            name="مصالح شاهد",
            unit_of_measure=unit,
        )

    def contract(self, *, with_item=False):
        party = create_business_party(
            organization=self.organization,
            actor=self.owner,
            party_kind="company",
            display_name="طرف آزمون",
        )
        contract = create_contract(
            organization=self.organization,
            actor=self.owner,
            project=self.project,
            party=party,
            contract_number="PH3-C",
            title="قرارداد شاهد",
            counterparty_name=party.display_name,
            direction="payable",
            contract_type="subcontract",
            contract_value=Decimal(1000),
        )
        if with_item:
            self.item = add_contract_item(
                organization=self.organization,
                actor=self.owner,
                contract=contract,
                description="کار قابل اندازه‌گیری",
                quantity=Decimal(10),
                unit_price=Decimal(100),
            )
        transition_contract_status(
            organization=self.organization,
            actor=self.owner,
            contract=contract,
            status="active",
        )
        contract.refresh_from_db()
        return contract

    def contractual(self):
        return create_contractual_record(
            organization=self.organization,
            actor=self.owner,
            contract=self.contract(),
            kind="claim",
            record_number="PH3-CR",
            title="رکورد قراردادی شاهد",
            description="شاهد بدون اثر خودکار",
            idempotency_key="ph3-contractual",
        )

    def url(self, action, kind, target, version=None):
        return reverse(
            "documents:evidence-" + action,
            args=[kind, target.pk, *([version.pk] if version else [])],
        )

    def form(self, kind, target):
        response = self.client.get(self.url("register", kind, target))
        self.assertEqual(response.status_code, 200)
        return response, Page(response.content.decode()).hidden

    def register(self, kind, target, version, **extra):
        _, hidden = self.form(kind, target)
        key = "versions" if kind in {"safety", "quality"} else "version"
        return self.client.post(
            self.url("register", kind, target),
            {
                **hidden,
                key: [str(version.pk)] if key == "versions" else str(version.pk),
                "reason": "ارسال برای بررسی",
                "label": "شاهد قراردادی",
                **extra,
            },
        )

    def panel(self, kind, target, user=None):
        return evidence_panel(
            user=user or self.owner,
            organization=self.organization,
            kind=kind,
            identifier=target.pk,
        )

    def test_safety_and_quality_submit_revision_evidence_and_keep_v1_after_v2(self):
        self.login()
        document = self._create_document()
        first = document.current_version
        self.clean_version(first)
        targets = (("safety", self.safety()), ("quality", self.quality()))
        for kind, target in targets:
            with self.subTest(kind=kind):
                result = self.register(kind, target, first)
                self.assertRedirects(
                    result,
                    self.panel(kind, target).source.url,
                    fetch_redirect_response=False,
                )
                revision = target.review_revisions.get()
                self.assertEqual(revision.evidence.get().document_version_id, first.pk)
                target.refresh_from_db()
                self.assertEqual(target.status, "reported")
                self.assertEqual(target.review_status, "submitted")
                with self.assertRaises(ValidationError):
                    revision.delete()
                with self.assertRaises(ValidationError):
                    revision.evidence.get().delete()
                self.assertEqual(
                    self.client.get(self.url("register", kind, target)).status_code, 403
                )
        second = add_document_version(
            document=document, actor=self.owner, upload=self._pdf_upload(suffix=b"v2")
        )
        self.assertFalse(second.is_available)
        for kind, target in targets:
            row = self.panel(kind, target).rows[0]
            self.assertEqual((row.version, row.current_version), (1, 2))
            self.assertIn(str(first.pk), row.download_url)
            detail = self.client.get(row.view_url)
            self.assertContains(detail, "نسخه شاهد")
            self.assertContains(detail, "نسخه جاری سند")
            self.assertNotIn(
                str(first.pk), " ".join(Page(detail.content.decode()).visible)
            )
            download = self.client.get(row.download_url)
            self.assertEqual(download.status_code, 200)
            self.assertTrue(b"".join(download.streaming_content).startswith(b"%PDF"))

    def test_observation_draft_picker_preserves_pin_and_idempotency(self):
        self.login()
        observation = self.observation()
        document = self._create_document()
        version = document.current_version
        self.clean_version(version)
        _, hidden = self.form("field_observation", observation)
        data = {**hidden, "version": str(version.pk)}
        endpoint = self.url("register", "field_observation", observation)
        self.assertEqual(self.client.post(endpoint, data).status_code, 302)
        self.assertEqual(self.client.post(endpoint, data).status_code, 302)
        self.assertEqual(observation.evidence_links.count(), 1)
        submit_field_observation(
            organization=self.organization,
            actor=self.owner,
            observation_id=observation.pk,
            operation_key=uuid4(),
        )
        add_document_version(
            document=document, actor=self.owner, upload=self._pdf_upload(suffix=b"new")
        )
        panel = self.panel("field_observation", observation)
        self.assertEqual(panel.rows[0].version, 1)
        self.assertFalse(panel.register_url)
        self.assertEqual(self.client.post(endpoint, data).status_code, 403)
        response = self.client.get(panel.source.url)
        self.assertContains(response, "شواهد و مستندات")
        self.assertNotContains(response, "شناسه نسخه DMS")
        self.assertNotContains(response, version.sha256)

    def test_contractual_witness_is_draft_only_and_survives_submission(self):
        self.login()
        target = self.contractual()
        document = self._create_document()
        result = self.register("contractual", target, document.current_version)
        self.assertEqual(result.status_code, 302)
        evidence = target.evidence_links.get()
        self.assertEqual(evidence.document_version_id, document.current_version_id)
        self.reader(list(BusinessPermission.objects.values_list("code", flat=True)))
        submit_contractual_record(
            organization=self.organization, actor=self.owner, record=target
        )
        with self.assertRaises(ValidationError):
            evidence.delete()
        self.assertFalse(self.panel("contractual", target).register_url)
        self.assertEqual(
            self.client.get(self.url("register", "contractual", target)).status_code,
            403,
        )

    def test_material_existing_exact_version_navigation_keeps_pin_after_v2(self):
        self.login()
        material = self.material()
        document = self._create_document()
        version = document.current_version
        self.clean_version(version)
        add_document_link(document=document, actor=self.owner, target=material)
        add_document_version(
            document=document, actor=self.owner, upload=self._pdf_upload(suffix=b"v2")
        )
        panel = self.panel("material", material)
        self.assertEqual(panel.rows[0].version_id, version.pk)
        self.assertTrue(panel.register_url)
        response = self.client.get(panel.source.url)
        self.assertContains(response, 'href="#document-evidence"', count=1)
        self.assertContains(response, 'id="document-evidence"', count=1)
        self.assertContains(response, document.title)
        self.assertEqual(
            self.client.get(self.url("register", "material", material)).status_code, 200
        )

    def test_validation_cancel_and_forged_intent_preserve_context_without_writes(self):
        self.login()
        target = self.safety()
        response, hidden = self.form("safety", target)
        source = response.context["source"]
        self.assertEqual(self.client.get(source.url).status_code, 200)
        result = self.client.post(
            self.url("register", "safety", target), {**hidden, "reason": ""}
        )
        self.assertEqual(result.status_code, 400)
        self.assertContains(result, source.title, status_code=400)
        self.assertContains(result, source.url, status_code=400)
        result = self.client.post(
            self.url("register", "safety", target),
            {**hidden, "reason": "سبب", "context_token": "forged"},
        )
        self.assertEqual(result.status_code, 400)
        self.assertFalse(target.review_revisions.exists())

    def test_picker_filters_foreign_denied_project_and_all_context_documents(self):
        self.login()
        target = self.safety()
        allowed = self._create_document()
        other_project = Project.objects.create(
            organization=self.organization, code="DENIED-P", name="پروژه محدود"
        )
        hidden = self._create_document(
            reference="HIDDEN", title="DO NOT EXPOSE", target=other_project
        )
        foreign = self._create_document(
            organization=self.other_organization,
            actor=self.other_user,
            target=Project.objects.create(
                organization=self.other_organization, code="FOREIGN", name="Foreign"
            ),
            reference="FOREIGN",
        )
        reader = self.reader(
            [
                "safety_incidents.view",
                "safety_incidents.record_submit",
                "documents.view",
                "projects.view",
            ],
            project=self.project,
        )
        self.login(reader)
        endpoint = self.url("choices", "safety", target)
        result = self.client.get(endpoint)
        self.assertEqual(result.status_code, 200)
        text = result.content.decode()
        self.assertIn(allowed.title, text)
        self.assertNotIn(hidden.title, text)
        self.assertNotIn(str(foreign.current_version_id), text)
        self.assertEqual(
            self.client.get(endpoint, {"q": allowed.document_number}).json()["results"][
                0
            ]["value"],
            str(allowed.current_version_id),
        )
        add_document_link(document=allowed, actor=self.owner, target=other_project)
        self.assertEqual(self.client.get(endpoint).json()["results"], [])
        _, intent = self.form("safety", target)
        response = self.client.post(
            self.url("register", "safety", target),
            {**intent, "reason": "ثبت", "versions": [str(hidden.current_version_id)]},
        )
        self.assertEqual(response.status_code, 400)
        self.assertNotContains(response, hidden.title, status_code=400)

    def test_unauthorized_personas_cannot_read_titles_or_register(self):
        target = self.quality()
        document = self._create_document()
        self.login()
        self.register("quality", target, document.current_version)
        reader = self.reader(["quality_issues.view"], project=self.project)
        self.login(reader)
        self.assertIsNone(self.panel("quality", target, reader))
        self.assertEqual(
            self.client.get(
                self.url("detail", "quality", target, document.current_version)
            ).status_code,
            403,
        )
        response = self.client.get(reverse("quality:detail", args=[target.pk]))
        self.assertNotContains(response, document.title)
        self.assertNotContains(response, 'id="document-evidence"')

    def test_cross_tenant_sources_unsafe_returns_and_unpersisted_versions_denied(self):
        self.login()
        target = self.safety()
        document = self._create_document()
        self.assertEqual(
            self.client.get(
                self.url("detail", "safety", target, document.current_version)
            ).status_code,
            403,
        )
        for action in ("choices", "register"):
            self.assertEqual(
                self.client.get(
                    self.url(action, "safety", target),
                    {"next": "https://example.invalid"},
                ).status_code,
                403,
            )
        self.login(self.other_user)
        session = self.client.session
        session["active_organization_id"] = str(self.other_organization.pk)
        session.save()
        for action in ("choices", "register"):
            self.assertEqual(
                self.client.get(self.url(action, "safety", target)).status_code, 403
            )

    def test_archive_expiry_and_sealed_witnesses_expose_no_metadata(self):
        self.login()
        target = self.contractual()
        for index, (field, value) in enumerate(
            (
                ("archived_at", timezone.now()),
                ("access_expires_at", timezone.now() - timedelta(days=1)),
                ("retention_classification", "sealed_supplier_quote_evidence"),
            )
        ):
            document = self._create_document(reference=f"BLOCK-{index}")
            self.assertEqual(
                self.register(
                    "contractual", target, document.current_version
                ).status_code,
                302,
            )
            Document.objects.filter(pk=document.pk).update(**{field: value})
            self.assertEqual(
                self.client.get(
                    self.url("detail", "contractual", target, document.current_version)
                ).status_code,
                403,
            )
        self.assertEqual(self.panel("contractual", target).rows, ())

    def test_quarantine_is_visible_to_review_but_never_delivered_or_field_selectable(
        self,
    ):
        self.login()
        document = self._create_document()
        target = self.safety()
        self.assertEqual(
            self.register("safety", target, document.current_version).status_code, 302
        )
        row = self.panel("safety", target).rows[0]
        self.assertFalse(row.available)
        self.assertFalse(row.download_url)
        self.assertEqual(
            self.client.get(
                reverse(
                    "documents:version-download",
                    args=[document.pk, document.current_version_id],
                )
            ).status_code,
            403,
        )
        observation = self.observation()
        self.assertEqual(
            self.client.get(
                self.url("choices", "field_observation", observation)
            ).json()["results"],
            [],
        )

    def test_picker_has_no_authority_without_submission_permission(self):
        target = self.safety()
        reader = self.reader(
            ["safety_incidents.view", "documents.view", "projects.view"],
            project=self.project,
        )
        self.login(reader)
        self.assertFalse(self.panel("safety", target, reader).register_url)
        for action in ("choices", "register"):
            self.assertEqual(
                self.client.get(self.url(action, "safety", target)).status_code, 403
            )

    def test_csrf_and_transactional_authority_recheck(self):
        target = self.safety()
        client = self.login(client=Client(enforce_csrf_checks=True))
        self.assertEqual(
            client.post(self.url("register", "safety", target), {}).status_code, 403
        )
        self.login()
        _, hidden = self.form("safety", target)
        from apps.documents.evidence_views import _register

        def revoked(**kwargs):
            self.organization.memberships.filter(user=self.owner).update(
                status="inactive"
            )
            return _register(**kwargs)

        with patch("apps.documents.evidence_views._register", side_effect=revoked):
            response = self.client.post(
                self.url("register", "safety", target), {**hidden, "reason": "ارسال"}
            )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(target.review_revisions.exists())

    def commercial(self):
        self.contract = self.contract(with_item=True)
        self.manager = self.reader(
            list(BusinessPermission.objects.values_list("code", flat=True))
        )
        self.term = create_contract_term_version(
            organization=self.organization,
            actor=self.owner,
            contract=self.contract,
            effective_from=date(2026, 1, 1),
            retention_rate=Decimal(10),
            retention_cap=Decimal(100),
            retention_release_requirement="evidence_only",
            retention_release_cap=Decimal(100),
            reason="شرایط آزمایشی",
        )
        approve_contract_term_version(
            organization=self.organization,
            actor=self.manager,
            term_version=self.term,
            reason="تأیید مستقل",
        )
        commercial_fixture.CommercialControlFixture.approve_retained_certificate(self)
        self.evidence = self._create_document().current_version
        self.clean_version(self.evidence)
        guarantee = create_guarantee(
            organization=self.organization,
            actor=self.owner,
            contract=self.contract,
            guarantee_type="performance",
            exposure_side="received",
            instrument_reference="PH3-G",
            issuer_name="بانک آزمایشی",
            amount=Decimal(100),
            issued_on=date(2026, 1, 1),
            effective_from=date(2026, 1, 1),
            expiry_kind="dated",
            expires_on=date(2028, 1, 1),
            evidence_document_version=self.evidence,
            reason="ثبت شاهد",
        )
        compliance = create_compliance_evidence(
            organization=self.organization,
            actor=self.owner,
            contract=self.contract,
            evidence_kind="clearance",
            reference="PH3-CE",
            issuing_authority="مرجع آزمایشی",
            effective_from=date(2026, 1, 1),
            expiry_kind="dated",
            expires_on=date(2028, 1, 1),
            document_version=self.evidence,
            reason="ثبت شاهد",
        )
        release = create_retention_release(
            organization=self.organization,
            actor=self.owner,
            contract=self.contract,
            release_date=date(2026, 10, 1),
            amount=Decimal(10),
            evidence_document_version=self.evidence,
        )
        return [
            ("guarantee", guarantee),
            ("compliance", compliance),
            ("release", release),
        ]

    def test_all_three_commercial_witnesses_use_exact_version_and_no_uuid_labels(self):
        self.login()
        targets = self.commercial()
        add_document_version(
            document=self.evidence.document,
            actor=self.owner,
            upload=self._pdf_upload(suffix=b"v2"),
        )
        for kind, target in targets:
            with self.subTest(kind=kind):
                panel = self.panel(kind, target)
                self.assertEqual(panel.rows[0].version_id, self.evidence.pk)
                self.assertFalse(panel.register_url)
                response = self.client.get(panel.source.url)
                self.assertEqual(response.status_code, 200)
                visible = " ".join(Page(response.content.decode()).visible)
                self.assertNotIn(str(self.evidence.pk), visible)
                self.assertContains(response, "نسخه جاری سند")
                self.assertContains(response, 'href="#document-evidence"', count=1)
                self.assertEqual(
                    self.client.get(panel.rows[0].view_url).status_code, 200
                )

    def test_commercial_create_and_revision_pickers_are_scoped_searchable_exact_versions(
        self,
    ):
        self.login()
        targets = self.commercial()
        routes = {
            "guarantee": "billing:guarantee_create",
            "compliance": "billing:compliance_evidence_create",
            "release": "billing:retention_release_create",
        }
        for kind, target in targets:
            with self.subTest(kind=kind):
                response = self.client.get(reverse(routes[kind]))
                self.assertContains(response, "data-options-url")
                self.assertContains(response, "نسخه شاهد 1")
                endpoint = reverse("documents:commercial-evidence-choices", args=[kind])
                response = self.client.get(
                    endpoint, {"q": self.evidence.document.document_number}
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(
                    response.json()["results"][0]["value"], str(self.evidence.pk)
                )
                response = self.client.get(self.url("choices", kind, target))
                self.assertEqual(
                    response.json()["results"][0]["value"], str(self.evidence.pk)
                )
        from apps.billing.forms import GuaranteeRevisionForm

        form = GuaranteeRevisionForm(organization=self.organization)
        self.assertFalse(form.fields["evidence_document_version"].queryset.exists())

    def test_commercial_create_posts_preserve_selected_exact_version(self):
        self.login()
        self.commercial()
        base = {
            "contract": str(self.contract.pk),
            "reason": "ثبت شاهد دقیق",
            "evidence_document_version": str(self.evidence.pk),
        }
        cases = [
            (
                "billing:guarantee_create",
                {
                    **base,
                    "guarantee_type": "performance",
                    "exposure_side": "received",
                    "instrument_reference": "PH3-HTTP-G",
                    "issuer_name": "بانک نمونه",
                    "amount": "100",
                    "issued_on": "2026-01-01",
                    "effective_from": "2026-01-01",
                    "expiry_kind": "dated",
                    "expires_on": "2028-01-01",
                },
                "guarantee",
            ),
            (
                "billing:compliance_evidence_create",
                {
                    **base,
                    "document_version": str(self.evidence.pk),
                    "evidence_kind": "clearance",
                    "reference": "PH3-HTTP-C",
                    "issuing_authority": "مرجع نمونه",
                    "effective_from": "2026-01-01",
                    "expiry_kind": "dated",
                    "expires_on": "2028-01-01",
                },
                "compliance",
            ),
            (
                "billing:retention_release_create",
                {**base, "release_date": "2026-10-01", "amount": "10"},
                "release",
            ),
        ]
        from apps.billing.models import (
            ContractComplianceEvidence,
            ContractGuarantee,
            RetentionRelease,
        )

        models = {
            "guarantee": ContractGuarantee,
            "compliance": ContractComplianceEvidence,
            "release": RetentionRelease,
        }
        for route, values, kind in cases:
            with self.subTest(kind=kind):
                response = self.client.post(reverse(route), values)
                self.assertEqual(
                    response.status_code, 302, getattr(response, "context", None)
                )
                target = models[kind].objects.order_by("-created_at").first()
                self.assertEqual(
                    self.panel(kind, target).rows[0].version_id, self.evidence.pk
                )

    def test_commercial_revision_posts_keep_original_witness_and_finalized_history(
        self,
    ):
        self.login()
        targets = self.commercial()
        from apps.billing.commercial_services import (
            decide_compliance_evidence,
            decide_guarantee,
            decide_retention_release,
            submit_compliance_evidence,
            submit_guarantee,
            submit_retention_release,
        )

        operations = {
            "guarantee": (
                submit_guarantee,
                decide_guarantee,
                "guarantee",
                "billing:guarantee_revise",
            ),
            "compliance": (
                submit_compliance_evidence,
                decide_compliance_evidence,
                "evidence",
                "billing:compliance_evidence_revise",
            ),
            "release": (
                submit_retention_release,
                decide_retention_release,
                "release",
                "billing:retention_release_correct",
            ),
        }
        second = add_document_version(
            document=self.evidence.document,
            actor=self.owner,
            upload=self._pdf_upload(suffix=b"v2"),
        )
        self.clean_version(second)
        for kind, target in targets:
            with self.subTest(kind=kind):
                submit, decide, argument, route = operations[kind]
                submit(
                    organization=self.organization,
                    actor=self.owner,
                    **{argument: target},
                )
                decide(
                    organization=self.organization,
                    actor=self.manager,
                    approved=True,
                    reason="تأیید مستقل",
                    **{argument: target},
                )
                target.refresh_from_db()
                values = {
                    "reason": "اصلاح با شاهد جدید",
                    "evidence_document_version": str(second.pk),
                    "document_version": str(second.pk),
                    "revision_action": "correction",
                    "correction_kind": "replacement",
                    "amount": "10",
                    "reference": "PH3-REVISED-C",
                    "issuing_authority": "مرجع جدید",
                    "effective_from": "2026-01-01",
                    "expiry_kind": "dated",
                    "expires_on": "2028-01-01",
                }
                response = self.client.post(reverse(route, args=[target.pk]), values)
                self.assertEqual(response.status_code, 302)
                revised = (
                    type(target)
                    .objects.filter(
                        **{"corrects" if kind == "release" else "predecessor": target}
                    )
                    .get()
                )
                self.assertEqual(
                    self.panel(kind, revised).rows[0].version_id, second.pk
                )
                self.assertEqual(
                    self.panel(kind, target).rows[0].version_id, self.evidence.pk
                )

    def test_site_scope_picker_is_available_only_for_own_observation(self):
        self.login()
        observation = self.observation()
        document = self._create_document(target=observation.site)
        self.clean_version(document.current_version)
        other_project = Project.objects.create(
            organization=self.organization, code="SITE-DENIED", name="پروژه دیگر"
        )
        other_site = ProjectSite.objects.create(
            organization=self.organization,
            project=other_project,
            code="SITE-DENIED",
            name="کارگاه دیگر",
        )
        other = create_field_observation(
            organization=self.organization,
            actor=self.owner,
            project=other_project,
            site=other_site,
            kind="general",
            title="مشاهده محدود",
            operation_key=uuid4(),
        )
        reader = self.reader(
            [
                "field_observations.view",
                "field_observations.capture",
                "documents.view",
                "projects.view",
                "project_sites.view",
            ],
            site=observation.site,
        )
        self.login(reader)
        self.assertEqual(
            self.client.get(
                self.url("choices", "field_observation", observation)
            ).json()["results"][0]["value"],
            str(document.current_version_id),
        )
        for action in ("choices", "register"):
            self.assertEqual(
                self.client.get(
                    self.url(action, "field_observation", other)
                ).status_code,
                403,
            )

    def test_download_permission_is_rechecked_separately_from_evidence_view(self):
        self.login()
        target = self.safety()
        document = self._create_document()
        self.clean_version(document.current_version)
        self.assertEqual(
            self.register("safety", target, document.current_version).status_code, 302
        )
        reader = self.reader(
            ["safety_incidents.view", "documents.view", "projects.view"],
            project=self.project,
        )
        self.login(reader)
        row = self.panel("safety", target, reader).rows[0]
        self.assertTrue(row.available)
        self.assertFalse(row.download_url)
        self.assertEqual(self.client.get(row.view_url).status_code, 200)
        self.assertEqual(
            self.client.get(
                reverse(
                    "documents:version-download",
                    args=[document.pk, document.current_version_id],
                )
            ).status_code,
            403,
        )

    def test_review_registration_rolls_back_on_domain_audit_failure(self):
        self.login()
        target = self.safety()
        document = self._create_document()
        with patch(
            "apps.safety.record_review.record_audit_event",
            side_effect=ValidationError("INTERNAL-AUDIT-ERROR"),
        ):
            response = self.register("safety", target, document.current_version)
        self.assertEqual(response.status_code, 400)
        self.assertNotContains(response, "INTERNAL-AUDIT-ERROR", status_code=400)
        self.assertFalse(target.review_revisions.exists())
        target.refresh_from_db()
        self.assertEqual(target.review_status, "draft")

    def test_material_registration_rejects_current_version_drift_and_keeps_exact_pin(
        self,
    ):
        self.login()
        target = self.material()
        document = self._create_document()
        first = document.current_version
        _, intent = self.form("material", target)
        second = add_document_version(
            document=document, actor=self.owner, upload=self._pdf_upload(suffix=b"v2")
        )
        response = self.client.post(
            self.url("register", "material", target),
            {**intent, "version": str(first.pk)},
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(target.document_links.exists())
        self.assertEqual(self.register("material", target, second).status_code, 302)
        self.assertEqual(target.document_links.get().document_version_id, second.pk)
        self.assertEqual(
            self.client.get(self.url("choices", "material", target)).json()["results"],
            [],
        )
        self.assertFalse(self.panel("material", target).rows[0].download_url)

    def test_material_registration_rechecks_version_after_form_validation(self):
        self.login()
        target = self.material()
        document = self._create_document()
        first = document.current_version
        _, intent = self.form("material", target)
        from apps.documents.evidence_registration import register_evidence

        def advanced(**kwargs):
            add_document_version(
                document=document,
                actor=self.owner,
                upload=self._pdf_upload(suffix=b"v2"),
            )
            return register_evidence(**kwargs)

        with patch("apps.documents.evidence_views._register", side_effect=advanced):
            response = self.client.post(
                self.url("register", "material", target),
                {**intent, "version": str(first.pk)},
            )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(target.document_links.exists())
