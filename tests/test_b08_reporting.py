"""B08 reporting dates follow the organization without changing retained facts."""

from datetime import UTC, datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.organizations.models import OrganizationSettings
from apps.reporting import test_p10_s02_s06 as reporting_fixture
from apps.reporting.models import MetricResult
from apps.reporting.services import refresh_metric
from core.jalali import format_jalali


@override_settings(PRODUCT_SURFACE_PROFILE="MVP")
class ReportingOrganizationTimezoneTests(TestCase):
    setUpTestData = classmethod(
        reporting_fixture.P10S02S06AcceptanceTests.setUpTestData.__func__
    )
    _grant = classmethod(reporting_fixture.P10S02S06AcceptanceTests._grant.__func__)

    def test_midnight_dates_use_configured_zone_without_rewriting_source(self):
        stamp = datetime(2026, 11, 20, 21, 15, tzinfo=UTC)
        self.client.force_login(self.user)
        session = self.client.session
        session["active_organization_id"] = str(self.organization.pk)
        session.save()
        with patch("django.utils.timezone.now", return_value=stamp):
            result = refresh_metric(
                organization=self.organization,
                actor=self.user,
                metric_code="procurement_cycle_time",
                idempotency_key="b08-timezone-empty-source",
            )
            saved = MetricResult.objects.get(pk=result.pk)
            for zone in ("Asia/Tehran", "UTC"):
                with self.subTest(zone=zone):
                    OrganizationSettings.objects.update_or_create(
                        organization=self.organization, defaults={"timezone": zone}
                    )
                    expected = format_jalali(
                        stamp.astimezone(ZoneInfo(zone)).replace(tzinfo=None),
                        include_time=True,
                    )
                    with (
                        timezone.override("UTC"),
                        CaptureQueriesContext(connection) as queries,
                    ):
                        response = self.client.get(reverse("reporting:dashboard"))
                        self.assertEqual(timezone.get_current_timezone_name(), "UTC")
                    self.assertContains(response, expected, count=4)
                    self.assertEqual(
                        [
                            query["sql"]
                            for query in queries
                            if query["sql"].split()[0].upper()
                            in {"INSERT", "UPDATE", "DELETE"}
                            and "django_session" not in query["sql"]
                        ],
                        [],
                    )
                    result.refresh_from_db()
                    self.assertEqual(result.as_of, saved.as_of)
                    self.assertEqual(result.value, saved.value)
                    self.assertEqual(result.source_manifest, saved.source_manifest)
