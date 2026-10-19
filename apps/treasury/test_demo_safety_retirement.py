"""Human-authorized demo Safety closure through the unchanged domain review."""

from datetime import timedelta

from django.utils import timezone

from apps.accounts.management.commands.seed_demo_data import Command
from apps.safety import tests as safety_tests
from apps.safety.models import SafetyIncident, SafetyIncidentStatus, SafetyReviewStatus


class DemoSafetyRetirementTests(safety_tests.SafetyTestBase):
    def test_demo_closure_retains_separate_record_review_and_is_idempotent(self):
        command = Command()
        command._ensure_system_catalog()
        arguments = {
            "organization_index": 1,
            "project_index": 1,
            "organization": self.organization,
            "owner": self.owner,
            "manager": self.owner,
            "project": self.project,
            "site": self.site,
            "phase": self.phase,
            "activity": self.activity,
            "responsible_party": self.party,
            "start": timezone.localdate() - timedelta(days=20),
        }
        command._seed_safety_incident(**arguments)
        incident = SafetyIncident.objects.get(
            organization=self.organization, incident_number="SAF-01-01-01"
        )
        self.assertEqual(incident.status, SafetyIncidentStatus.CLOSED)
        self.assertEqual(incident.review_status, SafetyReviewStatus.APPROVED)
        revisions = list(incident.review_revisions.order_by("sequence"))
        self.assertEqual(
            [(r.prior_state, r.state) for r in revisions],
            [("draft", "submitted"), ("submitted", "approved")],
        )
        self.assertIn("2026-10-20", revisions[-1].reason)
        self.assertEqual(revisions[-1].actor_id, self.owner.pk)
        self.assertIsNotNone(incident.closed_at)
        command._seed_safety_incident(**arguments)
        self.assertEqual(incident.review_revisions.count(), 2)
        self.assertEqual(SafetyIncident.objects.count(), 1)
