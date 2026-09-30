from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.materials.models import QuantityRoundingMode, UnitDimension
from apps.materials.services import (
    assign_unit_to_family,
    configure_unit_family,
    convert_quantity,
    create_quantity_rounding_policy_version,
    create_unit_conversion_version,
    create_unit_of_measure,
)
from apps.organizations.models import MembershipRole, MembershipStatus, Organization


class P1S24VersionedUnitConversionTests(TestCase):
    def setUp(self) -> None:
        self.owner = User.objects.create_user(username="s24-owner")
        self.other_owner = User.objects.create_user(username="s24-other-owner")
        self.organization = Organization.objects.create(name="S24", slug="s24")
        self.other_organization = Organization.objects.create(
            name="S24 Other", slug="s24-other"
        )
        for organization, user in (
            (self.organization, self.owner),
            (self.other_organization, self.other_owner),
        ):
            organization.memberships.create(
                user=user,
                role=MembershipRole.COMPANY_OWNER,
                status=MembershipStatus.ACTIVE,
            )
        self.metre = create_unit_of_measure(
            organization=self.organization,
            actor=self.owner,
            code="M",
            name="Metre",
            symbol="m",
            category="length",
            decimal_places=2,
        )
        self.centimetre = create_unit_of_measure(
            organization=self.organization,
            actor=self.owner,
            code="CM",
            name="Centimetre",
            symbol="cm",
            category="length",
            decimal_places=0,
        )
        self.length = configure_unit_family(
            organization=self.organization,
            actor=self.owner,
            base_unit=self.metre,
            code="LENGTH",
            name="Length",
            dimension=UnitDimension.LENGTH,
        )
        assign_unit_to_family(
            organization=self.organization,
            actor=self.owner,
            unit=self.centimetre,
            family=self.length,
        )

    def test_effective_versions_and_snapshots_preserve_historical_factor(self) -> None:
        now = timezone.now()
        first_start = now - timedelta(days=3)
        revision_at = now - timedelta(days=1)
        first = create_unit_conversion_version(
            organization=self.organization,
            actor=self.owner,
            unit=self.centimetre,
            factor_to_base=Decimal("0.01"),
            effective_from=first_start,
            effective_until=revision_at,
            source_reference="P1 test source v1",
        )
        second = create_unit_conversion_version(
            organization=self.organization,
            actor=self.owner,
            unit=self.centimetre,
            factor_to_base=Decimal("0.02"),
            effective_from=revision_at,
            source_reference="P1 test source v2",
        )
        historic = convert_quantity(
            organization=self.organization,
            actor=self.owner,
            quantity=Decimal(100),
            input_unit=self.centimetre,
            output_unit=self.metre,
            context_key="purchase-request-item:historic",
            at=first_start + timedelta(hours=1),
        )
        current = convert_quantity(
            organization=self.organization,
            actor=self.owner,
            quantity=Decimal(100),
            input_unit=self.centimetre,
            output_unit=self.metre,
            context_key="purchase-request-item:current",
            at=now,
        )
        self.assertEqual(historic.output_quantity, Decimal(1))
        self.assertEqual(historic.input_conversion_version, first)
        self.assertEqual(current.output_quantity, Decimal(2))
        self.assertEqual(current.input_conversion_version, second)
        historic.output_quantity = Decimal(3)
        with self.assertRaises(ValidationError):
            historic.save()

    def test_rounding_is_required_and_pinned_when_target_precision_is_insufficient(self) -> None:
        millimetre = create_unit_of_measure(
            organization=self.organization,
            actor=self.owner,
            code="MM",
            name="Millimetre",
            symbol="mm",
            category="length",
        )
        assign_unit_to_family(
            organization=self.organization,
            actor=self.owner,
            unit=millimetre,
            family=self.length,
        )
        effective_from = timezone.now() - timedelta(minutes=1)
        create_unit_conversion_version(
            organization=self.organization,
            actor=self.owner,
            unit=millimetre,
            factor_to_base=Decimal("0.001"),
            effective_from=effective_from,
            source_reference="P1 test source",
        )
        with self.assertRaisesMessage(ValueError, "سیاست گرد کردن موردنیاز تنظیم نشده است."):
            convert_quantity(
                organization=self.organization,
                actor=self.owner,
                quantity=Decimal(1),
                input_unit=millimetre,
                output_unit=self.metre,
                context_key="daily-report-entry:missing-policy",
                at=timezone.now(),
            )
        policy = create_quantity_rounding_policy_version(
            organization=self.organization,
            actor=self.owner,
            code="MEASUREMENTS",
            scale=2,
            mode=QuantityRoundingMode.HALF_UP,
            effective_from=effective_from,
        )
        snapshot = convert_quantity(
            organization=self.organization,
            actor=self.owner,
            quantity=Decimal(1),
            input_unit=millimetre,
            output_unit=self.metre,
            context_key="daily-report-entry:rounded",
            at=timezone.now(),
            rounding_policy=policy,
        )
        self.assertEqual(snapshot.output_quantity, Decimal("0.00"))
        self.assertEqual(snapshot.rounding_policy_version, policy)

    def test_cross_tenant_or_incompatible_units_fail_closed(self) -> None:
        other_unit = create_unit_of_measure(
            organization=self.other_organization,
            actor=self.other_owner,
            code="M",
            name="Other metre",
            symbol="m",
            category="length",
        )
        with self.assertRaises(PermissionDenied):
            assign_unit_to_family(
                organization=self.organization,
                actor=self.owner,
                unit=self.centimetre,
                family=other_unit.family,
            )
        with self.assertRaises(PermissionDenied):
            convert_quantity(
                organization=self.organization,
                actor=self.owner,
                quantity=Decimal(1),
                input_unit=self.centimetre,
                output_unit=other_unit,
                context_key="cross-tenant",
            )
