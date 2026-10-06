from datetime import date
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.accounts.models import User
from apps.organizations.models import (
    MembershipRole,
    MembershipStatus,
    Organization,
    OrganizationSettings,
)
from apps.parties.models import BusinessParty, PartyKind
from apps.partner_qualification.models import QualificationStatus
from apps.partner_qualification.services import (
    calculate_score,
    create_profile,
    create_qualification,
    publish_requirement,
    transition_qualification,
)


class PartnerQualificationP9S12S15Tests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(username="partner-author", password="x")
        self.reviewer = User.objects.create_user(
            username="partner-reviewer", password="x"
        )
        self.organization = Organization.objects.create(
            name="Partner P9",
            slug="partner-p9",
            created_by=self.author,
            updated_by=self.author,
        )
        OrganizationSettings.objects.create(organization=self.organization)
        for user, role in (
            (self.author, MembershipRole.COMPANY_OWNER),
            (self.reviewer, MembershipRole.COMPANY_MANAGER),
        ):
            self.organization.memberships.create(
                user=user, role=role, status=MembershipStatus.ACTIVE
            )
        self.party = BusinessParty.objects.create(
            organization=self.organization,
            party_kind=PartyKind.COMPANY,
            display_name="همکار",
        )

    def test_versioned_requirement_profile_and_fail_closed_category(self):
        profile = create_profile(
            organization=self.organization, actor=self.author, party=self.party
        )
        requirement = publish_requirement(
            organization=self.organization,
            actor=self.author,
            code="HSE",
            title="ایمنی",
            category_code="civil",
            source_reference="rule",
            source_version="1",
        )
        qualification = create_qualification(
            organization=self.organization,
            actor=self.author,
            profile=profile,
            requirement=requirement,
            reference_number="REF-1",
            valid_from=date(2026, 1, 1),
            valid_until=date(2026, 12, 1),
        )
        self.assertEqual(qualification.status, QualificationStatus.DRAFT)
        with self.assertRaises(ValidationError):
            transition_qualification(
                organization=self.organization,
                actor=self.author,
                qualification_id=qualification.pk,
                expected_status=QualificationStatus.DRAFT,
                to_status=QualificationStatus.APPROVED,
                reason="",
                operation_key=uuid4(),
            )

    def test_score_is_explainable_and_bounded(self):
        score, explanation = calculate_score(
            [{"code": "quality", "weight": 60}, {"code": "time", "weight": 40}],
            {"quality": 80, "time": 50},
        )
        self.assertEqual(str(score), "68.00")
        self.assertEqual(len(explanation), 64)
        with self.assertRaises(ValidationError):
            calculate_score([{"code": "quality", "weight": 99}], {"quality": 80})
