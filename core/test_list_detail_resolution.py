"""Focused HTTP boundaries for the classified List-to-Detail gaps."""

from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import User
from apps.compliance.models import InspectionTemplate
from apps.equipment.models import Equipment, MaintenanceRecord
from apps.equipment.p8_models import EquipmentWorkOrder
from apps.fixed_assets.models import (
    AssetBookPolicyVersion,
    AssetTransaction,
    FixedAsset,
    FixedAssetClassVersion,
)
from apps.organizations.models import (
    AuthorizationScopeType,
    MembershipRole,
    MembershipScopeGrant,
    MembershipStatus,
    Organization,
    OrganizationSettings,
)
from apps.organizations.services import ACTIVE_ORGANIZATION_SESSION_KEY
from apps.parties.models import BusinessParty
from apps.partner_qualification.models import (
    PartnerEvaluation,
    PartnerProfile,
    PartnerQualification,
    QualificationRequirement,
)
from apps.projects.models import Project, ProjectSite
from apps.subledgers.models import Obligation
from apps.timekeeping.models import (
    AttendanceCorrectionRequest,
    AttendanceRecord,
    LeaveMissionRequest,
    OvertimeRequest,
    WorkCalendar,
)
from apps.workforce.models import Employee


class ReadOnlyDetailBoundaryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="detail-owner")
        cls.reader = User.objects.create_user(username="detail-scoped")
        cls.unscoped = User.objects.create_user(username="detail-no-grant")
        cls.org = Organization.objects.create(
            name="Navigation tenant", slug="detail-tenant", created_by=cls.owner
        )
        cls.other = Organization.objects.create(
            name="Foreign navigation tenant", slug="detail-other", created_by=cls.owner
        )
        cls.member = cls.org.memberships.create(
            user=cls.owner,
            role=MembershipRole.COMPANY_OWNER,
            status=MembershipStatus.ACTIVE,
        )
        MembershipScopeGrant.objects.create(
            organization=cls.org,
            membership=cls.member,
            scope_type=AuthorizationScopeType.ORGANIZATION,
            reason="Navigation fixture",
        )
        cls.org.memberships.create(
            user=cls.unscoped,
            role=MembershipRole.COMPANY_OWNER,
            status=MembershipStatus.ACTIVE,
        )
        cls.project = Project.objects.create(
            organization=cls.org,
            code="NAV-1",
            name="Visible project",
            created_by=cls.owner,
        )
        cls.hidden_project = Project.objects.create(
            organization=cls.org,
            code="NAV-2",
            name="Other project",
            created_by=cls.owner,
        )
        cls.foreign_project = Project.objects.create(
            organization=cls.other,
            code="NAV-X",
            name="Foreign project",
            created_by=cls.owner,
        )
        reader_member = cls.org.memberships.create(
            user=cls.reader,
            role=MembershipRole.COMPANY_OWNER,
            status=MembershipStatus.ACTIVE,
        )
        MembershipScopeGrant.objects.create(
            organization=cls.org,
            membership=reader_member,
            scope_type=AuthorizationScopeType.PROJECT,
            project=cls.project,
            reason="Only the explicitly assigned project is visible",
        )
        cls.employee = Employee.objects.create(
            organization=cls.org,
            employee_number="NAV-E",
            first_name="نمونه",
            last_name="آزمایشی",
        )
        calendar = WorkCalendar.objects.create(
            organization=cls.org,
            code="NAV-C",
            name="Navigation calendar",
            timezone=cls.org.timezone,
            effective_from=date(2026, 1, 1),
            working_weekdays=[1, 2, 3, 4, 5],
            created_by=cls.owner,
        )
        cls.sites = []
        cls.maintenance = []
        cls.time_records = []
        for index, project in enumerate(
            (cls.project, cls.hidden_project, cls.foreign_project)
        ):
            org = project.organization
            site = ProjectSite.objects.create(
                organization=org,
                project=project,
                code=f"SITE-{index}",
                name=f"Navigation site {index}",
                created_by=cls.owner,
            )
            equipment = Equipment.objects.create(
                organization=org,
                code=f"EQ-{index}",
                name=f"Navigation equipment {index}",
                category="Navigation fixture",
            )
            maintenance = MaintenanceRecord.objects.create(
                organization=org,
                equipment=equipment,
                project=project,
                site=site,
                record_number=f"MR-{index}",
                summary="Navigation maintenance",
                created_by=cls.owner,
                maintenance_type=MaintenanceRecord._meta.get_field(
                    "maintenance_type"
                ).choices[0][0],
                scheduled_date=date(2026, 10, 26),
            )
            cls.sites.append(site)
            cls.maintenance.append(maintenance)
            if org == cls.org:
                record = AttendanceRecord.objects.create(
                    organization=org,
                    employee=cls.employee,
                    project=project,
                    site=site,
                    work_date=date(2026, 10, 26) + timedelta(days=index),
                    captured_by=cls.owner,
                    calendar=calendar,
                    source="manual",
                    check_in_at=datetime(2026, 10, 26 + index, 8, tzinfo=timezone.utc),
                )
                cls.time_records.append(record)
        cls.order = EquipmentWorkOrder.objects.create(
            organization=cls.org,
            equipment=cls.maintenance[0].equipment,
            number="WO-NAV",
            summary="Navigation order",
            created_by=cls.owner,
        )
        cls.template = InspectionTemplate.objects.create(
            organization=cls.org,
            profile="hse",
            code="NAV-T",
            title="Navigation checklist",
            created_by=cls.owner,
        )
        cls.correction = AttendanceCorrectionRequest.objects.create(
            organization=cls.org,
            attendance=cls.time_records[0],
            kind="reversal",
            reason="Navigation fixture",
            requested_by=cls.owner,
        )
        start = datetime(2026, 10, 26, 8, tzinfo=timezone.utc)
        cls.leave = LeaveMissionRequest.objects.create(
            organization=cls.org,
            employee=cls.employee,
            project=cls.project,
            site=cls.sites[0],
            kind="leave",
            category_code="annual",
            starts_at=start,
            ends_at=start + timedelta(hours=1),
            reason="Navigation fixture",
            requested_by=cls.owner,
        )
        cls.overtime = OvertimeRequest.objects.create(
            organization=cls.org,
            employee=cls.employee,
            project=cls.project,
            site=cls.sites[0],
            starts_at=start,
            ends_at=start + timedelta(hours=1),
            reason="Navigation fixture",
            requested_by=cls.owner,
        )

        cls.hidden_correction = AttendanceCorrectionRequest.objects.create(
            organization=cls.org,
            attendance=cls.time_records[1],
            kind="reversal",
            reason="Navigation scope fixture",
            requested_by=cls.owner,
        )
        cls.hidden_leave = LeaveMissionRequest.objects.create(
            organization=cls.org,
            employee=cls.employee,
            project=cls.hidden_project,
            site=cls.sites[1],
            kind="leave",
            category_code="annual",
            starts_at=start,
            ends_at=start + timedelta(hours=1),
            reason="Navigation scope fixture",
            requested_by=cls.owner,
        )
        cls.hidden_overtime = OvertimeRequest.objects.create(
            organization=cls.org,
            employee=cls.employee,
            project=cls.hidden_project,
            site=cls.sites[1],
            starts_at=start,
            ends_at=start + timedelta(hours=1),
            reason="Navigation scope fixture",
            requested_by=cls.owner,
        )

    def login(self, user):
        self.client.force_login(user)
        session = self.client.session
        session[ACTIVE_ORGANIZATION_SESSION_KEY] = str(self.org.pk)
        session.save()

    def urls(self):
        return [
            reverse("projects:site_detail", args=[self.project.pk, self.sites[0].pk]),
            reverse("equipment:maintenance_detail", args=[self.maintenance[0].pk]),
            reverse("equipment:work_order_detail", args=[self.order.pk]),
            reverse("organizations:member_detail", args=[self.member.pk]),
            reverse("compliance:template_detail", args=[self.template.pk]),
            *[
                reverse("timekeeping:record_detail", args=[kind, record.pk])
                for kind, record in (
                    ("attendance", self.time_records[0]),
                    ("correction", self.correction),
                    ("leave", self.leave),
                    ("overtime", self.overtime),
                )
            ],
        ]

    @override_settings(PRODUCT_SURFACE_PROFILE="FULL_ERP")
    def test_resolution_details_are_get_only_read_views(self):
        self.login(self.owner)
        for url in self.urls():
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(
                    response, "components/read_only_record_detail.html"
                )
                main = (
                    response.content.decode()
                    .split("<main", 1)[1]
                    .split("</main>", 1)[0]
                )
                self.assertNotIn("<form", main)
                self.assertEqual(self.client.post(url, {}).status_code, 405)

    @override_settings(PRODUCT_SURFACE_PROFILE="FULL_ERP")
    def test_resolution_financial_partner_details_read_only_and_tenant_scoped(self):
        self.login(self.owner)
        for organization, project in (
            (self.org, self.project),
            (self.other, self.foreign_project),
        ):
            OrganizationSettings.objects.get_or_create(organization=organization)
            membership = organization.memberships.filter(user=self.owner).first()
            if membership is None:
                membership = organization.memberships.create(
                    user=self.owner, role=MembershipRole.COMPANY_OWNER
                )
            common = {"organization": organization, "prepared_by": self.owner}
            asset_class = FixedAssetClassVersion.objects.create(
                **common,
                code="NAV",
                name="Navigation class",
                version=1,
                effective_from=date(2026, 1, 1),
                account_mapping_reference="NAV",
                capitalization_policy_reference="NAV",
            )
            book = AssetBookPolicyVersion.objects.create(
                **common,
                code="NAV",
                version=1,
                effective_from=date(2026, 1, 1),
                monetary_policy_code="NAV",
                monetary_policy_version="1",
                convention="daily_prorata",
            )
            asset = FixedAsset.objects.create(
                **common,
                asset_number="NAV-FA",
                name="Navigation asset",
                asset_class=asset_class,
                book_policy=book,
                ready_for_use_date=date(2026, 1, 1),
                useful_life_months=12,
                residual_value=0,
                capitalization_basis=100,
                evidence_reference="NAV",
                project=project,
            )
            transaction = AssetTransaction.objects.create(
                **common,
                asset=asset,
                transaction_type="opening",
                occurred_on=date(2026, 1, 1),
                amount=100,
                occurrence_key="NAV",
                reason="Navigation fixture",
            )
            obligation = Obligation.objects.create(
                organization=organization,
                direction="payable",
                source_kind="NAV",
                source_uuid=uuid4(),
                source_version=1,
                source_status="recorded",
                source_hash="a" * 64,
                source_snapshot={"fixture": True},
                party_name_snapshot="Navigation party",
                project=project,
                original_amount=100,
                recognized_on=date(2026, 1, 1),
                idempotency_key="NAV",
                payload_hash="b" * 64,
                recognized_by=membership,
            )
            party = BusinessParty.objects.create(
                organization=organization,
                party_kind="company",
                display_name="Navigation partner",
            )
            profile = PartnerProfile.objects.create(
                organization=organization,
                party=party,
                created_by=self.owner,
            )
            requirement = QualificationRequirement.objects.create(
                organization=organization,
                code="NAV",
                version=1,
                title="Navigation",
                category_code="NAV",
                source_reference="Navigation fixture",
                source_version="1",
                published_by=self.owner,
                canonical_hash="c" * 64,
            )
            qualification = PartnerQualification.objects.create(
                organization=organization,
                profile=profile,
                requirement=requirement,
                reference_number="NAV-Q",
            )
            evaluation = PartnerEvaluation.objects.create(
                organization=organization,
                profile=profile,
                project=project,
                period_start=date(2026, 1, 1),
                period_end=date(2026, 1, 31),
                criteria_snapshot=[{"code": "NAV"}],
                scores={"NAV": 1},
                authored_by=self.owner,
            )
            urls = [
                reverse("fixed_assets:transaction_detail", args=[transaction.pk]),
                reverse("subledgers:obligation_detail", args=[obligation.pk]),
                reverse(
                    "partner_qualification:record_detail",
                    args=["qualification", qualification.pk],
                ),
                reverse(
                    "partner_qualification:record_detail",
                    args=["evaluation", evaluation.pk],
                ),
            ]
            for url in urls:
                with self.subTest(url=url, tenant=organization.slug):
                    response = self.client.get(url)
                    self.assertEqual(
                        response.status_code, 200 if organization == self.org else 404
                    )
                    if organization == self.org:
                        self.assertTemplateUsed(
                            response, "components/read_only_record_detail.html"
                        )
                        self.assertNotIn(
                            "<form",
                            response.content.decode()
                            .split("<main", 1)[1]
                            .split("</main>", 1)[0],
                        )
                        self.assertEqual(self.client.post(url, {}).status_code, 405)

    def test_resolution_known_foreign_and_mismatched_project_records_are_denied(self):
        self.login(self.owner)
        urls = [
            reverse(
                "projects:site_detail", args=[self.foreign_project.pk, self.sites[2].pk]
            ),
            reverse("equipment:maintenance_detail", args=[self.maintenance[2].pk]),
            reverse("projects:site_detail", args=[self.project.pk, self.sites[1].pk]),
        ]
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 404)

    def test_resolution_project_scope_is_rechecked_for_direct_ids(self):
        self.login(self.reader)
        for project, site, record, attendance in (
            (self.project, self.sites[0], self.maintenance[0], self.time_records[0]),
            (
                self.hidden_project,
                self.sites[1],
                self.maintenance[1],
                self.time_records[1],
            ),
        ):
            for url in (
                reverse("projects:site_detail", args=[project.pk, site.pk]),
                reverse("equipment:maintenance_detail", args=[record.pk]),
                reverse(
                    "timekeeping:record_detail", args=["attendance", attendance.pk]
                ),
            ):
                self.assertEqual(
                    self.client.get(url).status_code,
                    200 if project == self.project else 404,
                )

        for kind, visible, hidden in (
            ("correction", self.correction, self.hidden_correction),
            ("leave", self.leave, self.hidden_leave),
            ("overtime", self.overtime, self.hidden_overtime),
        ):
            self.assertEqual(
                self.client.get(
                    reverse("timekeeping:record_detail", args=[kind, visible.pk])
                ).status_code,
                200,
            )
            self.assertEqual(
                self.client.get(
                    reverse("timekeeping:record_detail", args=[kind, hidden.pk])
                ).status_code,
                404,
            )

    def test_resolution_no_scope_never_grants_read_access(self):
        self.login(self.unscoped)
        for url in self.urls():
            self.assertIn(self.client.get(url).status_code, (302, 403, 404))

    @override_settings(PRODUCT_SURFACE_PROFILE="FULL_ERP")
    def test_resolution_financial_partner_and_unknown_kind_routes_fail_closed(self):
        self.login(self.owner)
        for url in (
            reverse("fixed_assets:transaction_detail", args=[uuid4()]),
            reverse("subledgers:obligation_detail", args=[uuid4()]),
            reverse(
                "partner_qualification:record_detail", args=["qualification", uuid4()]
            ),
            reverse(
                "partner_qualification:record_detail", args=["evaluation", uuid4()]
            ),
            reverse(
                "partner_qualification:record_detail", args=["unregistered", uuid4()]
            ),
            reverse("timekeeping:record_detail", args=["unregistered", uuid4()]),
        ):
            self.assertEqual(self.client.get(url).status_code, 404)
            self.assertEqual(self.client.post(url, {}).status_code, 405)
