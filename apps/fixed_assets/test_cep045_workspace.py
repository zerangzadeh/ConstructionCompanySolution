"""Read-only workspace boundaries using explicit current authorization fixtures."""

from datetime import date
from uuid import uuid4

from django.core.exceptions import PermissionDenied
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounting import test_cep042_recognition as recognition
from apps.accounting.models import JournalEntry
from apps.accounting.recognition_models import SourceRecognitionDraft
from apps.accounting.test_cep042_regression import explicit_fixture_authority
from apps.accounts.models import User
from apps.equipment.models import Equipment
from apps.organizations.models import (
    BusinessPermission,
    MembershipScopeGrant,
    OrganizationRole,
)
from apps.organizations.models import (
    BusinessPermissionCode as P,
)
from apps.organizations.services import (
    ACTIVE_ORGANIZATION_SESSION_KEY,
    create_organization_with_owner,
)
from apps.projects.models import Project, ProjectSite
from apps.treasury.models import TreasuryMovement
from core.home import authorized_home_links

from .models import (
    AssetBookPolicyVersion,
    FixedAsset,
    FixedAssetClassVersion,
    FixedAssetEquipmentLink,
)
from .workspace import visible_assets

READ_CODES = (
    P.FIXED_ASSETS_VIEW,
    P.EQUIPMENT_VIEW,
    P.EQUIPMENT_ASSIGNMENTS_VIEW,
    P.MAINTENANCE_RECORDS_VIEW,
    P.EQUIPMENT_OPERATIONS_VIEW,
    P.FINANCIALS_VIEW,
    P.ACCOUNTING_VIEW,
    P.TREASURY_VIEW,
    P.SUBLEDGERS_VIEW,
    P.EXPENSES_VIEW,
    P.ACCOUNTING_RECOGNITION_VIEW,
)


def explicit_reader(organization, username, codes=READ_CODES):
    actor = User.objects.create_user(username=username, password="synthetic-cep045")
    role = OrganizationRole.objects.create(
        organization=organization, code=username, name="Explicit test reader"
    )
    role.permissions.set(BusinessPermission.objects.filter(code__in=codes))
    membership = organization.memberships.create(
        user=actor, role="member", role_definition=role, status="active"
    )
    explicit_fixture_authority(membership, role)
    return actor, membership, role


class WorkspaceFixture:
    def setUp(self):
        super().setUp()
        self.owner = User.objects.create_user(username="cep045-owner")
        self.organization = create_organization_with_owner(
            owner=self.owner, name="شرکت آزمایشی تفکیک حوزه‌ها", slug="cep045"
        )
        self.actor, self.membership, self.role = explicit_reader(
            self.organization, "cep045-reader"
        )
        self.equipment = Equipment.objects.create(
            organization=self.organization,
            code="SAME045",
            name="تجهیز عملیاتی آزمایشی",
            category="سازه",
        )
        self.asset = self.make_asset(self.organization, self.owner)
        self.client.force_login(self.actor)
        session = self.client.session
        session[ACTIVE_ORGANIZATION_SESSION_KEY] = str(self.organization.pk)
        session.save()

    def make_asset(self, organization, owner):
        cls = FixedAssetClassVersion.objects.create(
            organization=organization,
            code="CLASS045",
            name="طبقهٔ آزمایشی",
            version=1,
            status="published",
            effective_from=date(2026, 1, 1),
            account_mapping_reference="Synthetic retained map",
            capitalization_policy_reference="Synthetic retained policy",
            prepared_by=owner,
        )
        book = AssetBookPolicyVersion.objects.create(
            organization=organization,
            code="BOOK045",
            version=1,
            status="published",
            effective_from=date(2026, 1, 1),
            monetary_policy_code="accounting-money-precision",
            monetary_policy_version="1",
            convention="full_month",
            prepared_by=owner,
        )
        return FixedAsset.objects.create(
            organization=organization,
            asset_number="SAME045",
            name="دارایی مالی آزمایشی",
            asset_class=cls,
            book_policy=book,
            ready_for_use_date=date(2026, 1, 5),
            useful_life_months=12,
            residual_value=0,
            capitalization_basis=60,
            evidence_reference="Synthetic retained financial record",
            prepared_by=owner,
        )

    def link(self):
        return FixedAssetEquipmentLink.objects.create(
            organization=self.organization,
            asset=self.asset,
            equipment=self.equipment,
            effective_from=date(2026, 1, 5),
            reason="Explicit retained relationship; no identity inference",
            linked_by=self.owner,
        )

    def counts(self):
        return tuple(
            cls.objects.count()
            for cls in (
                Equipment,
                FixedAsset,
                FixedAssetEquipmentLink,
                TreasuryMovement,
                JournalEntry,
                SourceRecognitionDraft,
            )
        )


class WorkspaceSeparationTests(WorkspaceFixture, TestCase):
    def test_home_and_navigation_use_real_owning_capabilities_not_legacy_financials(
        self,
    ):
        links, _, _ = authorized_home_links(
            user=self.actor, organization=self.organization
        )
        routes = {item.route for item in links}
        self.assertNotIn("financials:dashboard", routes)
        self.assertIn("accounting:dashboard", routes)
        self.assertIn("treasury:workbench", routes)
        self.assertIn("fixed_assets:workbench", routes)
        self.assertIn("equipment:operations_workbench", routes)
        self.assertNotIn("equipment:list", routes)
        self.role.permissions.remove(
            BusinessPermission.objects.get(code=P.EQUIPMENT_OPERATIONS_VIEW)
        )
        links, _, _ = authorized_home_links(
            user=self.actor, organization=self.organization
        )
        self.assertIn("equipment:list", {item.route for item in links})
        response = self.client.get(reverse("equipment:list"))
        self.assertContains(response, 'data-workspace-id="WS-15A"')
        self.assertContains(response, f'href="{reverse("equipment:list")}"')
        self.assertEqual(
            self.client.get(reverse("equipment:operations_workbench")).status_code, 403
        )

    def test_separate_surfaces_and_read_requests_create_no_financial_or_identity_facts(
        self,
    ):
        before = self.counts()
        for route, identity in (
            ("equipment:operations_workbench", "WS-15A"),
            ("fixed_assets:workbench", "WS-15B"),
        ):
            response = self.client.get(reverse(route))
            self.assertContains(response, f'data-workspace-id="{identity}"')
            self.assertContains(response, '<html lang="fa" dir="rtl">')
        self.assertEqual(before, self.counts())
        response = self.client.get(reverse("fixed_assets:workbench"))
        self.assertNotContains(response, reverse("fixed_assets:asset_create"))
        self.assertContains(
            response, reverse("fixed_assets:asset_detail", args=[self.asset.pk])
        )

    def test_only_explicit_relationship_enables_cross_domain_drilldown(self):
        equipment_url = reverse("equipment:detail", args=[self.equipment.pk])
        asset_url = reverse("fixed_assets:asset_detail", args=[self.asset.pk])
        self.assertNotContains(self.client.get(equipment_url), asset_url)
        self.link()
        before = self.counts()
        self.assertContains(self.client.get(equipment_url), asset_url)
        response = self.client.get(asset_url)
        self.assertContains(response, equipment_url)
        self.assertContains(response, "1404/10/15")
        self.assertNotContains(response, "2026-01-05")
        self.assertEqual(before, self.counts())
        required = BusinessPermission.objects.get(code=P.EQUIPMENT_ASSIGNMENTS_VIEW)
        self.role.permissions.remove(required)
        self.assertNotContains(self.client.get(asset_url), equipment_url)
        self.role.permissions.add(required)
        self.role.permissions.remove(
            BusinessPermission.objects.get(code=P.EQUIPMENT_VIEW)
        )
        response = self.client.get(asset_url)
        self.assertNotContains(response, equipment_url)
        self.assertNotContains(response, self.equipment.name)

    def test_financial_permission_is_independent_of_equipment_and_job_title(self):
        self.link()
        self.role.permissions.remove(
            BusinessPermission.objects.get(code=P.FIXED_ASSETS_VIEW)
        )
        response = self.client.get(
            reverse("equipment:detail", args=[self.equipment.pk])
        )
        self.assertNotContains(response, self.asset.name)
        self.assertNotContains(
            response, reverse("fixed_assets:asset_detail", args=[self.asset.pk])
        )
        self.assertEqual(
            self.client.get(
                reverse("fixed_assets:asset_detail", args=[self.asset.pk])
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(
                reverse("fixed_assets:asset_detail", args=[uuid4()])
            ).status_code,
            403,
        )

    def test_foreign_tenant_and_invalid_context_do_not_reveal_objects(self):
        other_owner = User.objects.create_user(username="cep045-other")
        other = create_organization_with_owner(
            owner=other_owner, name="Private other organization", slug="other045"
        )
        foreign = self.make_asset(other, other_owner)
        for identity in (foreign.pk, uuid4()):
            response = self.client.get(
                reverse("fixed_assets:asset_detail", args=[identity]),
                {"organization_id": str(other.pk)},
            )
            self.assertEqual(response.status_code, 404)
            self.assertNotContains(response, foreign.name, status_code=404)
        self.assertEqual(
            self.client.get("/fixed-assets/assets/not-a-uuid/").status_code, 404
        )
        session = self.client.session
        session[ACTIVE_ORGANIZATION_SESSION_KEY] = str(other.pk)
        session.save()
        self.assertEqual(
            self.client.get(reverse("fixed_assets:workbench")).status_code, 403
        )

    def test_project_site_context_cannot_expand_existing_organization_only_permission(
        self,
    ):
        project = Project.objects.create(
            organization=self.organization, code="P045", name="Project"
        )
        site = ProjectSite.objects.create(
            organization=self.organization, project=project, code="S045", name="Site"
        )
        MembershipScopeGrant.objects.filter(membership=self.membership).update(
            revoked_at=timezone.now()
        )
        for scope, context in (
            ("project", {"project": project}),
            ("site", {"project": project, "site": site}),
        ):
            grant = MembershipScopeGrant.objects.create(
                organization=self.organization,
                membership=self.membership,
                scope_type=scope,
                reason="Explicit scoped fixture",
                **context,
            )
            with self.assertRaises(PermissionDenied):
                visible_assets(organization=self.organization, actor=self.actor)
            response = self.client.get(
                reverse("fixed_assets:workbench"),
                {"project_id": str(project.pk), "site_id": str(site.pk)},
            )
            self.assertEqual(response.status_code, 403)
            MembershipScopeGrant.objects.filter(pk=grant.pk).update(
                revoked_at=timezone.now()
            )

    def test_compatibility_projection_labels_sources_observation_and_authority_links(
        self,
    ):
        before = self.counts()
        for route in ("financials:dashboard", "financials:report"):
            response = self.client.get(reverse(route))
            self.assertContains(response, "نمای سازگاری مالی")
            self.assertContains(response, "اسناد قدیمی دریافت و پرداخت")
            self.assertContains(response, "زمان مشاهده")
            self.assertContains(response, reverse("treasury:workbench"))
            self.assertContains(response, reverse("accounting:dashboard"))
        self.assertEqual(before, self.counts())
        self.role.permissions.remove(
            BusinessPermission.objects.get(code=P.TREASURY_VIEW)
        )
        response = self.client.get(reverse("financials:dashboard"))
        self.assertNotContains(response, f'href="{reverse("treasury:workbench")}"')

    def test_empty_and_read_only_detail_states_are_explicit(self):
        response = self.client.get(
            reverse("fixed_assets:asset_detail", args=[self.asset.pk])
        )
        self.assertContains(response, "پیوند قابل‌نمایشی در دسترس نیست")
        self.assertContains(response, "منبعی ثبت نشده است")
        self.assertContains(response, "سند مرتبط قابل‌نمایشی در دسترس نیست")
        self.assertEqual(
            self.client.post(
                reverse("fixed_assets:asset_detail", args=[self.asset.pk])
            ).status_code,
            405,
        )


class AccountingDrilldownTests(recognition.RecognitionFixture, TestCase):
    def test_existing_native_recognition_is_linked_with_exact_source_version_and_no_new_writer(
        self,
    ):
        asset, transaction = self.asset()
        self.mapping("Fixed Assets", "capitalization")
        effect = self.recognize("asset", transaction)
        self.client.force_login(self.maker)
        before = (
            SourceRecognitionDraft.objects.count(),
            JournalEntry.objects.count(),
            TreasuryMovement.objects.count(),
        )
        response = self.client.get(
            reverse("fixed_assets:asset_detail", args=[asset.pk])
        )
        self.assertContains(
            response, reverse("accounting:journal_detail", args=[effect.journal_id])
        )
        self.assertContains(response, effect.source_version_reference)
        self.assertEqual(
            before,
            (
                SourceRecognitionDraft.objects.count(),
                JournalEntry.objects.count(),
                TreasuryMovement.objects.count(),
            ),
        )
        viewer, _, _ = explicit_reader(
            self.organization, "asset-only045", [P.FIXED_ASSETS_VIEW]
        )
        self.client.force_login(viewer)
        response = self.client.get(
            reverse("fixed_assets:asset_detail", args=[asset.pk])
        )
        self.assertNotContains(response, str(effect.journal_id))
        self.assertNotContains(response, effect.source_version_reference)
