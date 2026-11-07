from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

from apps.organizations.services import ACTIVE_ORGANIZATION_SESSION_KEY
from apps.projects.models import Project, ProjectPhase, ProjectSite
from apps.safety.forms import SafetyIncidentForm
from apps.safety.tests import SafetyTestBase


class SafetyContextChoiceTests(SafetyTestBase):
    def setUp(self):
        super().setUp()
        self.membership = self.organization.memberships.get(user=self.owner)
        self.payload = {
            "project": str(self.project.pk),
            "site": str(self.site.pk),
            "phase": str(self.phase.pk),
            "activity": str(self.activity.pk),
            "daily_report": str(self.daily_report.pk),
            "incident_number": "CASCADE-1",
            "occurred_at": (timezone.now() - timedelta(hours=1)).isoformat(),
            "incident_type": "near_miss",
            "severity": "low",
            "description": "Synthetic cascade verification",
        }

    def form(self, data=None, **kwargs):
        return SafetyIncidentForm(
            data=data,
            organization=self.organization,
            membership=kwargs.get("membership", self.membership),
        )

    def test_context_metadata_and_bound_labels(self):
        form = self.form(self.payload)
        self.assertTrue(form.is_valid(), form.errors)
        for name in ("site", "phase", "activity", "daily_report"):
            html = str(form[name])
            self.assertIn(f'data-project="{self.project.pk}"', html)
            self.assertIn(f'data-site="{self.site.pk}"', html)
            self.assertIn(f'value="{self.payload[name]}" selected', html)
        self.assertIn(self.phase.name, str(form["phase"]))
        self.assertIn(f'data-phase="{self.phase.pk}"', str(form["daily_report"]))

    def test_project_only_incident_and_project_level_activity_remain_valid(self):
        self.activity.site = None
        self.activity.phase = None
        self.activity.save(update_fields=["site", "phase"])
        form = self.form({**self.payload, "site": "", "phase": "", "daily_report": ""})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertIn('data-site="" data-phase=""', str(form["activity"]))

    def test_forged_cross_project_site_rejected(self):
        other = Project.objects.create(
            organization=self.organization, code="CASCADE-B", name="Other project"
        )
        form = self.form({**self.payload, "project": str(other.pk)})
        self.assertFalse(form.is_valid())
        self.assertIn("site", form.errors)

    def test_forged_sibling_site_phase_rejected(self):
        sibling = ProjectSite.objects.create(
            organization=self.organization,
            project=self.project,
            code="SIBLING",
            name="Sibling site",
        )
        form = self.form({**self.payload, "site": str(sibling.pk)})
        self.assertFalse(form.is_valid())
        self.assertIn("phase", form.errors)

    def test_activity_requires_its_selected_phase(self):
        form = self.form({**self.payload, "phase": "", "daily_report": ""})
        self.assertFalse(form.is_valid())
        self.assertIn("activity", form.errors)

    def test_report_requires_exact_phase_including_empty(self):
        form = self.form({**self.payload, "phase": "", "activity": ""})
        self.assertFalse(form.is_valid())
        self.assertIn("daily_report", form.errors)

    def test_cross_tenant_and_malformed_choices_rejected(self):
        foreign = Project.objects.create(
            organization=self.other_organization, code="FOREIGN", name="Foreign"
        )
        form = self.form({**self.payload, "project": str(foreign.pk), "site": "bad-id"})
        self.assertFalse(form.is_valid())
        self.assertIn("project", form.errors)
        self.assertIn("site", form.errors)
        self.assertNotIn(str(foreign.pk), str(form["project"]))

    def test_missing_or_foreign_membership_has_no_options(self):
        foreign = self.other_organization.memberships.get(user=self.other_owner)
        for membership in (None, foreign):
            form = self.form(membership=membership)
            for name in ("project", "site", "phase", "activity", "daily_report"):
                self.assertFalse(form.fields[name].queryset.exists())

    def test_archived_activity_and_inactive_site_excluded(self):
        self.activity.archived_at = timezone.now()
        self.activity.save(update_fields=["archived_at"])
        self.site.is_active = False
        self.site.save(update_fields=["is_active"])
        form = self.form(self.payload)
        self.assertNotIn(str(self.activity.pk), str(form["activity"]))
        self.assertNotIn(str(self.site.pk), str(form["site"]))
        self.assertFalse(form.is_valid())
        self.assertIn("site", form.errors)
        self.assertIn("activity", form.errors)

    def test_object_scope_applies_to_rendered_metadata(self):
        self.membership.scope_grants.all().delete()
        self.membership.scope_grants.create(
            organization=self.organization,
            scope_type="site",
            project=self.project,
            site=self.site,
            reason="Synthetic single site",
        )
        sibling = ProjectSite.objects.create(
            organization=self.organization,
            project=self.project,
            code="HIDDEN",
            name="Hidden site",
        )
        phase = ProjectPhase.objects.create(
            organization=self.organization,
            site=sibling,
            code="HIDDEN",
            name="Hidden phase",
        )
        form = self.form()
        self.assertNotIn(str(sibling.pk), str(form["site"]))
        self.assertNotIn(str(phase.pk), str(form["phase"]))

    def test_view_loads_scoped_cascade_and_denies_viewer(self):
        self.client.force_login(self.owner)
        session = self.client.session
        session[ACTIVE_ORGANIZATION_SESSION_KEY] = str(self.organization.pk)
        session.save()
        response = self.client.get(reverse("safety:create"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data-safety-context-form")
        self.assertContains(response, "safety/context_choices.js")
        invalid = self.client.post(
            reverse("safety:create"), {**self.payload, "description": ""}
        )
        self.assertEqual(invalid.status_code, 200)
        self.assertIn("description", invalid.context["form"].errors)
        for name in ("project", "site", "phase", "activity", "daily_report"):
            self.assertEqual(invalid.context["form"][name].value(), self.payload[name])
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.get(reverse("safety:create")).status_code, 403)
