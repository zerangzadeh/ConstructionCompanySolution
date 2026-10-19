"""Demo closure satisfies the unchanged Quality record approval contract."""

from datetime import timedelta

from django.utils import timezone

from apps.accounts.management.commands.seed_demo_data import Command
from apps.quality.models import QualityIssue, QualityReviewStatus
from apps.quality.tests import QualityTestBase


class DemoQualityRetirementTests(QualityTestBase):
    def test_seed_closure_has_review_snapshot_actor_reason_and_is_idempotent(self):
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
        command._seed_quality_issue(**arguments)
        issue = QualityIssue.objects.get(issue_number="QLT-01-01-01")
        self.assertEqual(issue.status, "closed")
        self.assertEqual(issue.review_status, QualityReviewStatus.APPROVED)
        revisions = list(issue.review_revisions.order_by("sequence"))
        self.assertEqual(
            [(r.prior_state, r.state) for r in revisions],
            [("draft", "submitted"), ("submitted", "approved")],
        )
        self.assertEqual(revisions[-1].actor_id, self.owner.pk)
        self.assertTrue(revisions[-1].reason)
        self.assertEqual(
            revisions[-1].snapshot["specification_reference"],
            issue.specification_reference,
        )
        command._seed_quality_issue(**arguments)
        self.assertEqual(issue.review_revisions.count(), 2)
        self.assertEqual(QualityIssue.objects.count(), 1)
