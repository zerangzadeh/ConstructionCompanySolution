from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.daily_reports.field_models import FieldObservation
from apps.daily_reports.services import create_daily_report, submit_daily_report
from apps.organizations.models import BusinessPermission, OrganizationRole
from apps.organizations.services import (
    ACTIVE_ORGANIZATION_SESSION_KEY,
    create_organization_with_owner,
)
from apps.projects.services import create_project, create_project_site
from apps.workflows.models import WorkflowInstance


class B03FieldOperationsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(username="b03-owner")
        cls.org = create_organization_with_owner(
            owner=cls.owner, name="B03 test company", slug="b03-test"
        )
        cls.org.settings.timezone = "Asia/Tehran"
        cls.org.settings.save(update_fields=["timezone"])
        cls.project = create_project(
            organization=cls.org, actor=cls.owner, code="P1", name="Project"
        )
        cls.site = create_project_site(
            organization=cls.org,
            project=cls.project,
            actor=cls.owner,
            code="S1",
            name="Site",
        )
        cls.sibling = create_project_site(
            organization=cls.org,
            project=cls.project,
            actor=cls.owner,
            code="S2",
            name="Sibling",
        )

    def login(self, user):
        self.client.force_login(user)
        session = self.client.session
        session[ACTIVE_ORGANIZATION_SESSION_KEY] = str(self.org.pk)
        session.save()

    def scoped_actor(self, username, site, *permissions):
        user = User.objects.create_user(username=username)
        role = OrganizationRole.objects.create(
            organization=self.org, code=username, name=username
        )
        role.permissions.set(BusinessPermission.objects.filter(code__in=permissions))
        membership = self.org.memberships.create(
            user=user, status="active", role_definition=role
        )
        membership.role_assignments.create(
            organization=self.org, role=role, reason="Test role"
        )
        membership.scope_grants.create(
            organization=self.org,
            scope_type="site",
            project=self.project,
            site=site,
            reason="Test site scope",
        )
        return user

    def observation_data(self):
        return {
            "project": self.project.pk,
            "site": self.site.pk,
            "kind": "general",
            "title": "B03 field observation",
            "captured_at": "1405/08/18 08:20",
            "effective_at": "2026-11-09T09:10",
            "location_permission": "granted",
            "latitude": "35.700000",
            "longitude": "51.400000",
            "horizontal_accuracy_meters": "20",
            "location_captured_at": "2026-11-09T08:19",
            "operation_key": uuid4(),
        }

    def create_observation(self, data):
        self.login(self.owner)
        response = self.client.post(
            reverse("daily_reports:field_observation_create"), data
        )
        self.assertEqual(response.status_code, 302)
        return FieldObservation.objects.get(title=data["title"])

    def test_wall_times_and_stale_draft_retries(self):
        data = self.observation_data()
        observation = self.create_observation(data)
        self.assertEqual(
            observation.captured_at, datetime(2026, 11, 9, 4, 50, tzinfo=UTC)
        )
        self.assertEqual(
            observation.effective_at, datetime(2026, 11, 9, 5, 40, tzinfo=UTC)
        )
        self.assertEqual(
            observation.location_captured_at, datetime(2026, 11, 9, 4, 49, tzinfo=UTC)
        )
        detail = reverse(
            "daily_reports:field_observation_detail", args=[observation.pk]
        )
        self.assertContains(self.client.get(detail), "1405/08/18 08:20")
        save = reverse("daily_reports:field_observation_save", args=[observation.pk])
        edit = {
            **data,
            "expected_revision": observation.revision,
            "operation_key": uuid4(),
            "summary": "Newer draft",
        }
        for attempt in (edit, edit):
            self.assertEqual(self.client.post(save, attempt).status_code, 302)
        stale = self.client.post(
            save, {**edit, "operation_key": uuid4(), "summary": "Stale draft"}
        )
        self.assertContains(stale, "پیش‌نویس قدیمی است")
        observation.refresh_from_db()
        self.assertEqual(
            (observation.revision, observation.summary), (2, "Newer draft")
        )

    def test_scoped_editor_can_edit_without_reading_or_changing_coordinates(self):
        data = self.observation_data()
        observation = self.create_observation(data)
        editor = self.scoped_actor(
            "b03-editor",
            self.site,
            "field_observations.view",
            "field_observations.capture",
        )
        self.login(editor)
        list_url = reverse("daily_reports:field_observation_list")
        detail = reverse(
            "daily_reports:field_observation_detail", args=[observation.pk]
        )
        self.assertContains(self.client.get(list_url), observation.title)
        self.assertNotContains(self.client.get(detail), "35.700000")
        response = self.client.post(
            reverse("daily_reports:field_observation_save", args=[observation.pk]),
            {
                **data,
                "expected_revision": observation.revision,
                "operation_key": uuid4(),
                "summary": "Scoped edit",
                "latitude": "36.000000",
            },
        )
        self.assertEqual(response.status_code, 302)
        observation.refresh_from_db()
        self.assertEqual(observation.latitude, Decimal("35.700000"))
        self.assertEqual(observation.summary, "Scoped edit")
        sibling = self.scoped_actor(
            "b03-sibling", self.sibling, "field_observations.view"
        )
        self.login(sibling)
        self.assertNotContains(self.client.get(list_url), observation.title)
        self.assertEqual(self.client.get(detail).status_code, 403)

    def test_site_scoped_daily_report_approval_uses_existing_work_item(self):
        permissions = (
            "daily_reports.view",
            "daily_reports.approve",
            "work_items.view",
            "work_items.claim",
            "work_items.act",
        )
        reviewer = self.scoped_actor("b03-reviewer", self.site, *permissions)
        wrong = self.scoped_actor("b03-other-reviewer", self.sibling, *permissions)
        report = create_daily_report(
            organization=self.org,
            project=self.project,
            site=self.site,
            actor=self.owner,
            reporting_date=date(2026, 11, 9),
            work_performed="B03 work",
        )
        submit_daily_report(
            organization=self.org, actor=self.owner, report_id=report.pk
        )
        approve = reverse("daily_reports:approve", args=[report.pk])
        self.login(wrong)
        self.assertEqual(self.client.post(approve).status_code, 403)
        self.login(reviewer)
        self.assertEqual(self.client.post(approve).status_code, 302)
        report.refresh_from_db()
        instance = WorkflowInstance.objects.get(subject_id=report.pk)
        self.assertEqual(
            (report.status, report.approved_by_id), ("approved", reviewer.pk)
        )
        self.assertEqual(instance.work_items.get().status, "completed")

    def test_invalid_inline_entry_preserves_input_and_canonical_print_link(self):
        report = create_daily_report(
            organization=self.org,
            project=self.project,
            site=self.site,
            actor=self.owner,
            reporting_date=date(2026, 11, 9),
            work_performed="B03 work",
        )
        self.login(self.owner)
        response = self.client.post(
            reverse("daily_reports:labor_add", args=[report.pk]),
            {"team_name": "B03 crew", "worker_count": "4", "hours_worked": "999999999"},
        )
        self.assertContains(response, 'value="B03 crew"')
        self.assertContains(response, 'aria-invalid="true"')
        detail = reverse("daily_reports:detail", args=[report.pk])
        self.assertContains(response, f'href="{detail}?format=print"')
        self.assertFalse(report.labor_entries.exists())
