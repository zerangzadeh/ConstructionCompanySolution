"""BATCH-09: independent site-aware selector, HTTP and service matrices."""

import re
from datetime import timedelta
from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.audit.models import AuditEvent
from apps.daily_reports.models import DailyReport
from apps.equipment.forms import MaintenanceRecordForm
from apps.equipment.models import Equipment, MaintenanceRecord
from apps.equipment.services import create_maintenance_record
from apps.organizations.authorization import membership_has_scope
from apps.organizations.models import (
    MembershipRoleAssignment,
    MembershipScopeGrant,
    Organization,
    OrganizationMembership,
    OrganizationRole,
    OrganizationSettings,
)
from apps.organizations.services import ACTIVE_ORGANIZATION_SESSION_KEY
from apps.parties.models import BusinessParty
from apps.projects.models import Activity, Project, ProjectPhase, ProjectSite, WBSNode
from apps.quality.forms import QualityIssueForm
from apps.quality.models import QualityIssue
from apps.quality.services import create_quality_issue
from apps.safety.forms import SafetyIncidentForm
from apps.safety.models import SafetyIncident
from apps.safety.services import create_safety_incident


class OperationalScopeMatrix:
    @classmethod
    def member(cls, user, org, role="project_manager", organization_scope=False):
        member = OrganizationMembership.objects.create(
            user=user,
            organization=org,
            role=role,
            status="active",
            authorization_migrated_at=timezone.now(),
        )
        MembershipRoleAssignment.objects.create(
            organization=org,
            membership=member,
            role=OrganizationRole.objects.get(code=role),
            reason="Disposable B09",
        )
        if organization_scope:
            MembershipScopeGrant.objects.create(
                organization=org,
                membership=member,
                scope_type="organization",
                reason="Disposable B09 organization control",
            )
        return member

    @classmethod
    def setUpTestData(cls):
        cls.org = Organization.objects.create(name="B09 tenant", slug="b09")
        cls.other = Organization.objects.create(name="B09 foreign", slug="b09-x")
        for org in (cls.org, cls.other):
            OrganizationSettings.objects.create(organization=org, currency="IRR")
        cls.user = User.objects.create_user(username="b09-limited")
        cls.owner = User.objects.create_user(username="b09-owner")
        cls.foreign = User.objects.create_user(username="b09-foreign")
        cls.site_user = User.objects.create_user(username="b09-site")
        cls.viewer = User.objects.create_user(username="b09-viewer")
        cls.limited = cls.member(cls.user, cls.org)
        cls.owner_member = cls.member(cls.owner, cls.org, "company_owner", True)
        cls.foreign_member = cls.member(cls.foreign, cls.other, "company_owner", True)
        cls.site_member = cls.member(cls.site_user, cls.org, "operations_manager")
        cls.viewer_member = cls.member(cls.viewer, cls.org, "viewer", True)
        cls.sources = {}
        for key in "ABCDX":
            org = cls.other if key == "X" else cls.org
            project = Project.objects.create(
                organization=org,
                code=f"B09-P-{key}",
                name=f"B09 distinctive Project {key}",
            )
            wbs = WBSNode.objects.create(
                organization=org,
                project=project,
                code=f"B09-W-{key}",
                title=f"B09 WBS {key}",
            )
            cls.sources[key] = {"project": project}
            for suffix in ("", "2"):
                site = ProjectSite.objects.create(
                    organization=org,
                    project=project,
                    code=f"B09-S-{key}{suffix}",
                    name=f"B09 distinctive Site {key}{suffix}",
                )
                phase = ProjectPhase.objects.create(
                    organization=org,
                    site=site,
                    code=f"B09-PH-{key}{suffix}",
                    name=f"B09 distinctive Phase {key}{suffix}",
                )
                activity = Activity.objects.create(
                    organization=org,
                    project=project,
                    site=site,
                    phase=phase,
                    wbs_node=wbs,
                    code=f"B09-ACT-{key}{suffix}",
                    name=f"B09 distinctive Activity {key}{suffix}",
                )
                report = DailyReport.objects.create(
                    organization=org,
                    project=project,
                    site=site,
                    phase=phase,
                    reporting_date=timezone.localdate(),
                    work_performed=f"B09 work {key}{suffix}",
                    created_by=cls.foreign if key == "X" else cls.owner,
                    updated_by=cls.foreign if key == "X" else cls.owner,
                )
                for field, obj in (
                    ("site", site),
                    ("phase", phase),
                    ("activity", activity),
                    ("daily_report", report),
                ):
                    cls.sources[key][field + suffix] = obj
            cls.sources[key]["project_activity"] = Activity.objects.create(
                organization=org,
                project=project,
                wbs_node=wbs,
                code=f"B09-PROJECT-ACT-{key}",
                name=f"B09 project-only Activity {key}",
            )
            if key in "AB":
                MembershipScopeGrant.objects.create(
                    organization=cls.org,
                    membership=cls.limited,
                    scope_type="project",
                    project=project,
                    reason="Disposable B09 A/B",
                )
        MembershipScopeGrant.objects.create(
            organization=cls.org,
            membership=cls.site_member,
            scope_type="site",
            project=cls.sources["A"]["project"],
            site=cls.sources["A"]["site"],
            reason="Disposable B09 site only",
        )
        cls.equipment = Equipment.objects.create(
            organization=cls.org,
            code="B09-E",
            name="B09 tenant equipment",
            category="B09",
        )
        cls.foreign_equipment = Equipment.objects.create(
            organization=cls.other,
            code="B09-E-X",
            name="B09 foreign equipment",
            category="B09",
        )
        cls.provider = BusinessParty.objects.create(
            organization=cls.org,
            display_name="B09 tenant provider",
            party_kind="company",
        )
        cls.foreign_provider = BusinessParty.objects.create(
            organization=cls.other,
            display_name="B09 foreign provider",
            party_kind="company",
        )

    @property
    def protected(self):
        return (
            ("project", "site")
            if self.model is MaintenanceRecord
            else ("project", "site", "phase", "activity", "daily_report")
        )

    def setUp(self):
        self.login()

    def login(self, user=None):
        self.client.force_login(user or self.user)
        session = self.client.session
        session[ACTIVE_ORGANIZATION_SESSION_KEY] = str(self.org.pk)
        session.save()

    def form(self, data=None, **kwargs):
        return self.form_class(
            data, organization=self.org, **({"membership": self.limited} | kwargs)
        )

    def payload(self, key="B"):
        data = {f: str(self.sources[key][f].pk) for f in self.protected}
        if self.model is MaintenanceRecord:
            return data | {
                "equipment": str(self.equipment.pk),
                "provider": str(self.provider.pk),
                "record_number": "B09-NEW",
                "maintenance_type": "preventive",
                "summary": "B09 synthetic maintenance",
                "scheduled_date": "1405/07/01",
            }
        return data | {
            self.number: "B09-NEW",
            self.timestamp: "2026-01-01T10:00",
            self.kind: "other",
            "severity": self.severity,
            "description": "B09 synthetic operational control",
        }

    def snapshot(self):
        return tuple(
            list(m.objects.order_by("pk").values())
            for m in (
                MaintenanceRecord,
                QualityIssue,
                SafetyIncident,
                AuditEvent,
            )
        )

    def expected(self, field, allowed="AB", site_only=False):
        if field == "project":
            return {self.sources[k][field] for k in allowed}
        result = set()
        for key in allowed:
            result.add(self.sources[key][field])
            if not site_only:
                result.add(self.sources[key][field + "2"])
                if field == "activity":
                    result.add(self.sources[key]["project_activity"])
        return result

    def assert_choices(self, form, allowed="AB", site_only=False):
        for field in self.protected:
            self.assertSetEqual(
                set(form.fields[field].queryset),
                self.expected(field, allowed, site_only),
                field,
            )

    def assert_safe(self, response, allowed="AB", site_only=False):
        self.assertEqual(response.status_code, 200)
        form = response.context["form"]
        self.assert_choices(form, allowed, site_only)
        body = re.sub(r'<input[^>]*name="next"[^>]*>', "", response.content.decode())
        body = re.sub(r'href="[^"]*[?&](?:amp;)?next=[^"]*"', "", body)
        for field in self.protected:
            permitted = self.expected(field, allowed, site_only)
            for row in self.sources.values():
                objects = (
                    [row[field]]
                    if field == "project"
                    else [row[field], row[field + "2"]]
                )
                if field == "activity":
                    objects.append(row["project_activity"])
                for obj in objects:
                    if obj in permitted:
                        self.assertIn(str(obj.pk), body)
                    else:
                        self.assertNotIn(str(obj.pk), body)
                        # Distinct codes/names disambiguate shared date/report labels.
                        for attr in ("code", "name"):
                            if hasattr(obj, attr):
                                self.assertNotIn(getattr(obj, attr), body)
        return form

    def create(self, actor, key="B", **overrides):
        form = self.form(self.payload(key), membership=self.owner_member)
        self.assertTrue(form.is_valid(), form.errors)
        return self.service(
            organization=self.org, actor=actor, **(form.cleaned_data | overrides)
        )

    def test_get_query_and_invalid_required_redisplay(self):
        self.assert_safe(self.client.get(reverse(self.route)))
        for key in "CDX":
            with self.subTest(query=key):
                self.assert_safe(
                    self.client.get(reverse(self.route), self.payload(key))
                )
        before = self.snapshot()
        for field, definition in self.form().fields.items():
            if definition.required:
                with self.subTest(required=field):
                    data = self.payload()
                    data.pop(field)
                    form = self.assert_safe(self.client.post(reverse(self.route), data))
                    self.assertIn(field, form.errors)
                    self.assertEqual(self.snapshot(), before)

    def test_all_protected_ids_same_tenant_cross_tenant_and_malformed(self):
        before = self.snapshot()
        for field in self.protected:
            for key in ("C", "D", "X", "invalid"):
                with self.subTest(field=field, key=key):
                    value = (
                        str(self.sources[key][field].pk) if key != "invalid" else key
                    )
                    form = self.assert_safe(
                        self.client.post(
                            reverse(self.route), self.payload() | {field: value}
                        )
                    )
                    self.assertIn(field, form.errors)
                    self.assertEqual(self.snapshot(), before)

    def test_site_only_exact_site_parent_context_no_siblings_or_project_activity(self):
        self.login(self.site_user)
        self.assert_safe(self.client.get(reverse(self.route)), "A", True)
        self.assertFalse(
            membership_has_scope(self.site_member, project=self.sources["A"]["project"])
        )
        before = self.snapshot()
        for field in self.protected:
            keys = ["B", "C", "D", "X"]
            for key in keys:
                with self.subTest(field=field, key=key):
                    form = self.assert_safe(
                        self.client.post(
                            reverse(self.route),
                            self.payload("A")
                            | {field: str(self.sources[key][field].pk)},
                        ),
                        "A",
                        True,
                    )
                    self.assertIn(field, form.errors)
                    self.assertEqual(self.snapshot(), before)
            if field != "project":
                form = self.assert_safe(
                    self.client.post(
                        reverse(self.route),
                        self.payload("A")
                        | {field: str(self.sources["A"][field + "2"].pk)},
                    ),
                    "A",
                    True,
                )
                self.assertIn(field, form.errors)
                self.assertEqual(self.snapshot(), before)
        if "activity" in self.protected:
            form = self.assert_safe(
                self.client.post(
                    reverse(self.route),
                    self.payload("A")
                    | {"activity": str(self.sources["A"]["project_activity"].pk)},
                ),
                "A",
                True,
            )
            self.assertIn("activity", form.errors)
            self.assertEqual(self.snapshot(), before)

    def test_mixed_authorized_project_site_and_children_rejected(self):
        before = self.snapshot()
        for field in self.protected[1:]:
            with self.subTest(field=field):
                form = self.assert_safe(
                    self.client.post(
                        reverse(self.route),
                        self.payload() | {field: str(self.sources["A"][field].pk)},
                    )
                )
                self.assertTrue(form.errors)
                self.assertEqual(self.snapshot(), before)
        if "phase" in self.protected:
            for field in ("phase", "activity", "daily_report"):
                with self.subTest(sibling=field):
                    form = self.assert_safe(
                        self.client.post(
                            reverse(self.route),
                            self.payload()
                            | {field: str(self.sources["B"][field + "2"].pk)},
                        )
                    )
                    self.assertIn(field, form.errors)
                    self.assertEqual(self.snapshot(), before)

    def test_service_rejection_redisplay_keeps_scope(self):
        before = self.snapshot()
        with patch(
            self.service_patch, side_effect=PermissionDenied("B09 service denial")
        ) as call:
            form = self.assert_safe(
                self.client.post(reverse(self.route), self.payload())
            )
            self.assertIn("B09 service denial", str(form.non_field_errors()))
            self.assertEqual(
                call.call_args.kwargs["project"], self.sources["B"]["project"]
            )
        self.assertEqual(self.snapshot(), before)

    def test_missing_wrong_tenant_and_invalid_membership_empty_all_fields(self):
        for member in (None, object(), self.foreign_member):
            for data in (None, self.payload()):
                with self.subTest(member=str(member), bound=bool(data)):
                    self.assert_choices(self.form(data, membership=member), "")

    def test_absent_grants_deny_http_and_empty_choices(self):
        self.limited.scope_grants.update(revoked_at=timezone.now())
        self.assert_choices(self.form(), "")
        self.assertEqual(self.client.get(reverse(self.route)).status_code, 403)

    def test_site_grant_effective_dates_and_revocation_fail_closed(self):
        self.login(self.site_user)
        grant = self.site_member.scope_grants.get()
        now = timezone.now()
        for values in (
            {"revoked_at": now},
            {"starts_at": now - timedelta(days=2), "ends_at": now - timedelta(days=1)},
            {"starts_at": now + timedelta(days=1)},
        ):
            with self.subTest(values=values):
                self.site_member.scope_grants.filter(pk=grant.pk).update(
                    **(
                        {
                            "revoked_at": None,
                            "starts_at": now - timedelta(days=3),
                            "ends_at": None,
                        }
                        | values
                    )
                )
                self.assert_choices(self.form(membership=self.site_member), "")
                self.assertEqual(self.client.get(reverse(self.route)).status_code, 403)

    def test_union_of_project_and_site_grants_preserves_exact_child_scope(self):
        MembershipScopeGrant.objects.create(
            organization=self.org,
            membership=self.site_member,
            scope_type="project",
            project=self.sources["B"]["project"],
            reason="Disposable B09 mixed-grant control",
        )
        self.login(self.site_user)
        response = self.client.get(reverse(self.route))
        self.assertEqual(response.status_code, 200)
        form = response.context["form"]
        for field in self.protected:
            self.assertSetEqual(
                set(form.fields[field].queryset),
                self.expected(field, "A", True) | self.expected(field, "B"),
            )
        before = self.snapshot()
        data = self.payload("A") | {"site": str(self.sources["A"]["site2"].pk)}
        response = self.client.post(reverse(self.route), data)
        self.assertIn("site", response.context["form"].errors)
        self.assertEqual(self.snapshot(), before)

    def test_revoked_expired_future_grants_exclude_all_children(self):
        grant = self.limited.scope_grants.get(project=self.sources["A"]["project"])
        now = timezone.now()
        for values in (
            {"revoked_at": now},
            {"starts_at": now - timedelta(days=2), "ends_at": now - timedelta(days=1)},
            {"starts_at": now + timedelta(days=1)},
        ):
            with self.subTest(values=values):
                self.limited.scope_grants.filter(pk=grant.pk).update(
                    **(
                        {
                            "revoked_at": None,
                            "starts_at": now - timedelta(days=3),
                            "ends_at": None,
                        }
                        | values
                    )
                )
                self.assert_choices(self.form(), "B")
                self.assert_safe(self.client.get(reverse(self.route)), "B")

    def test_inactive_membership_user_and_tenant_fail_closed(self):
        for obj, field, inactive, active in (
            (self.limited, "status", "inactive", "active"),
            (self.user, "is_active", False, True),
            (self.org, "status", "suspended", "active"),
        ):
            with self.subTest(field=field, obj=type(obj).__name__):
                setattr(obj, field, inactive)
                obj.save(update_fields=[field])
                self.assert_choices(self.form(), "")
                self.assertIn(
                    self.client.get(reverse(self.route)).status_code, (302, 403)
                )
                setattr(obj, field, active)
                obj.save(update_fields=[field])
                self.login()

    def test_scope_cannot_supply_role_or_capability(self):
        before = self.snapshot()
        self.login(self.viewer)
        self.assertEqual(self.client.get(reverse(self.route)).status_code, 403)
        with self.assertRaises(PermissionDenied):
            self.create(self.viewer)
        self.login()
        self.limited.role_assignments.update(revoked_at=timezone.now())
        self.assertEqual(self.client.get(reverse(self.route)).status_code, 403)
        with self.assertRaises(PermissionDenied):
            self.create(self.user)
        self.assertEqual(self.snapshot(), before)

    def test_organization_success_and_existing_limited_creation_gate(self):
        for actor, member, key, allowed, site_only in (
            (self.user, self.limited, "B", "AB", False),
            (self.owner, self.owner_member, "C", "ABCD", False),
            (self.site_user, self.site_member, "A", "A", True),
        ):
            with self.subTest(actor=actor.username):
                self.login(actor)
                self.assert_safe(
                    self.client.get(reverse(self.route)), allowed, site_only
                )
                data = self.payload(key)
                data[self.number] += "-" + key
                bound = self.form(data, membership=member)
                self.assertTrue(bound.is_valid(), bound.errors)
                before = self.snapshot()
                response = self.client.post(reverse(self.route), data)
                if self.model is not MaintenanceRecord and actor != self.owner:
                    # Existing workflow subject loaders require organization scope.
                    form = self.assert_safe(response, allowed, site_only)
                    self.assertTrue(form.non_field_errors())
                    self.assertEqual(self.snapshot(), before)
                    continue
                self.assertEqual(
                    response.status_code,
                    302,
                    getattr(response, "context", None)
                    and response.context["form"].errors,
                )
                record = self.model.objects.latest("created_at")
                self.assertEqual(record.project, self.sources[key]["project"])
                self.assertEqual(record.site, self.sources[key]["site"])
                self.assertEqual(record.status, self.initial_status)
                self.assertTrue(
                    AuditEvent.objects.filter(
                        entity_id=record.pk, action=self.audit
                    ).exists()
                )

    def test_direct_services_preserve_actual_scope_tenant_and_structure_checks(self):
        before = self.snapshot()
        for actor, keys in ((self.user, "CDX"), (self.site_user, "BCDX")):
            for key in keys:
                with self.subTest(actor=actor.username, key=key):
                    data = {f: self.sources[key][f] for f in self.protected}
                    with self.assertRaises(PermissionDenied):
                        self.create(actor, **data)
                    self.assertEqual(self.snapshot(), before)
        with self.assertRaises(PermissionDenied):
            self.create(
                self.site_user,
                "A",
                **{f: self.sources["A"][f + "2"] for f in self.protected[1:]},
            )
        self.assertEqual(self.snapshot(), before)
        for field in self.protected[1:]:
            with self.subTest(mixed_service=field):
                with self.assertRaises((ValueError, PermissionDenied)):
                    self.create(self.user, **{field: self.sources["A"][field]})
                self.assertEqual(self.snapshot(), before)

    def test_optional_children_and_project_only_activity_preserved(self):
        data = self.payload()
        for f in self.protected[1:]:
            data[f] = ""
        if self.model is MaintenanceRecord:
            data["project"] = ""
            before = self.snapshot()
            form = self.assert_safe(self.client.post(reverse(self.route), data))
            self.assertTrue(form.non_field_errors())
            self.assertEqual(self.snapshot(), before)
            self.login(self.owner)
        else:
            data["activity"] = str(self.sources["B"]["project_activity"].pk)
            self.login(self.owner)
        response = self.client.post(reverse(self.route), data)
        self.assertEqual(
            response.status_code,
            302,
            getattr(response, "context", None) and response.context["form"].errors,
        )
        record = self.model.objects.latest("created_at")
        self.assertIsNone(record.site)
        if self.model is MaintenanceRecord:
            self.assertIsNone(record.project)
        else:
            self.assertEqual(record.activity, self.sources["B"]["project_activity"])

    def test_original_lifecycle_predicates_and_master_visibility(self):
        site = self.sources["A"]["site2"]
        site.is_active = False
        site.save(update_fields=["is_active"])
        self.assertNotIn(site, self.form().fields["site"].queryset)
        if self.model is MaintenanceRecord:
            self.assertSetEqual(
                set(self.form().fields["equipment"].queryset), {self.equipment}
            )
            self.assertSetEqual(
                set(self.form().fields["provider"].queryset), {self.provider}
            )
            for field, source in (
                ("equipment", self.foreign_equipment),
                ("provider", self.foreign_provider),
            ):
                form = self.form(self.payload() | {field: str(source.pk)})
                self.assertFalse(form.is_valid())
                self.assertIn(field, form.errors)
            self.assertEqual(
                self.form().fields["project"].queryset.query.order_by, ("name",)
            )
        else:
            # No new active-site predicate is added to phase/activity/report catalogues.
            self.assertIn(
                self.sources["A"]["phase2"], self.form().fields["phase"].queryset
            )
            for attrs in ({"is_active": False}, {"archived_at": timezone.now()}):
                Activity.objects.filter(pk=self.sources["A"]["activity2"].pk).update(
                    **attrs
                )
                self.assertNotIn(
                    self.sources["A"]["activity2"],
                    self.form().fields["activity"].queryset,
                )
        project = self.sources["A"]["project"]
        project.deleted_at = timezone.now()
        project.save(update_fields=["deleted_at"])
        self.assertNotIn(project, self.form().fields["project"].queryset)


class MaintenanceOperationalScopeTests(OperationalScopeMatrix, TestCase):
    form_class = MaintenanceRecordForm
    model = MaintenanceRecord
    service = staticmethod(create_maintenance_record)
    service_patch = "apps.equipment.views.create_maintenance_record"
    route = "equipment:maintenance_create"
    number = "record_number"
    audit = "maintenance_record.created"
    initial_status = "scheduled"


class QualityOperationalScopeTests(OperationalScopeMatrix, TestCase):
    form_class = QualityIssueForm
    model = QualityIssue
    service = staticmethod(create_quality_issue)
    service_patch = "apps.quality.views.create_quality_issue"
    route = "quality:create"
    number = "issue_number"
    timestamp = "identified_at"
    kind = "issue_type"
    severity = "minor"
    audit = "quality_issue.created"
    initial_status = "reported"


class SafetyOperationalScopeTests(OperationalScopeMatrix, TestCase):
    form_class = SafetyIncidentForm
    model = SafetyIncident
    service = staticmethod(create_safety_incident)
    service_patch = "apps.safety.views.create_safety_incident"
    route = "safety:create"
    number = "incident_number"
    timestamp = "occurred_at"
    kind = "incident_type"
    severity = "low"
    audit = "safety_incident.created"
    initial_status = "reported"
