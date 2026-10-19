"""UI lifecycle and tenant authority over existing definition/version services."""

import json
from copy import deepcopy
from datetime import UTC, datetime
from uuid import uuid4

from django.test import Client, TestCase
from django.urls import reverse

from apps.accounting.test_cep042_regression import explicit_fixture_authority
from apps.accounts.models import User
from apps.audit.models import AuditAction, AuditEvent
from apps.organizations.models import (
    BusinessPermission,
    OrganizationRole,
    PlatformRoleAssignment,
)
from apps.organizations.services import create_organization_with_owner
from apps.projects.models import Project

from .administration import configuration_payload
from .models import (
    WorkflowDefinition,
    WorkflowInstance,
    WorkflowTemplate,
    WorkflowType,
    WorkflowVersion,
)
from .services import create_workflow_draft, edit_workflow_draft
from .tests import valid_configuration


class AdministrationFixture:
    def organization_factory(self, *, owner, name, slug):
        return create_organization_with_owner(owner=owner, name=name, slug=slug)

    def setUp(self):
        super().setUp()
        self.owner = User.objects.create_user(username="cep046-owner", password="test")
        self.organization = self.organization_factory(
            owner=self.owner, name="شرکت آزمایشی گردش‌کار", slug="cep046-company"
        )
        self.other = User.objects.create_user(username="cep046-other")
        self.other_organization = self.organization_factory(
            owner=self.other, name="Other046", slug="cep046-other"
        )
        self.workflow_type = WorkflowType.objects.get(
            code="procurement.purchase_request_approval"
        )
        self.login(self.owner)

    def login(self, actor):
        self.client.force_login(actor)
        session = self.client.session
        session["active_organization_id"] = str(self.organization.pk)
        session.save()

    def draft(self, *, foreign=False):
        return create_workflow_draft(
            actor=self.other if foreign else self.owner,
            organization=self.other_organization if foreign else self.organization,
            workflow_type_code=self.workflow_type.code,
            code="ordinary-admin",
            name="گردش‌کار آزمایشی محرمانه" if foreign else "گردش‌کار خرید آزمایشی",
        )

    def reader(self, codes=("workflows.view",), *, superuser=False):
        actor = User.objects.create_user(
            username=f"reader-{uuid4()}", is_staff=superuser, is_superuser=superuser
        )
        role = OrganizationRole.objects.create(
            organization=self.organization, code=f"role-{uuid4()}", name="Explicit test"
        )
        role.permissions.set(BusinessPermission.objects.filter(code__in=codes))
        membership = self.organization.memberships.create(
            user=actor, role_definition=role, role=role.code, status="active"
        )
        explicit_fixture_authority(membership, role)
        return actor, membership

    def action(self, version, action, **data):
        return self.client.post(
            reverse("workflows:version_action", args=[version.pk, action]), data
        )


class AdministrationTests(AdministrationFixture, TestCase):
    def test_registered_template_is_applied_verbatim_without_publication(self):
        version = self.draft()
        template = WorkflowTemplate.objects.create(
            workflow_type=self.workflow_type,
            code="synthetic-admin-template",
            name="الگوی آزمایشی ثبت‌شده",
            configuration=valid_configuration(),
        )
        response = self.client.post(
            reverse("workflows:version_edit", args=[version.pk]),
            {"template": str(template.pk)},
        )
        self.assertEqual(response.status_code, 302)
        version.refresh_from_db()
        self.assertEqual(version.status, "draft")
        self.assertEqual(version.steps.count(), len(template.configuration["steps"]))
        self.assertEqual(
            version.transitions.count(), len(template.configuration["transitions"])
        )
        self.assertEqual(
            version.steps.get(key="decision").configuration, {"decision_policy": "any"}
        )
        self.assertEqual(
            version.routing_rules.get().resolver_type, "organization_owner"
        )
        self.assertEqual(
            version.transitions.get(outcome="approved").domain_command,
            "procurement.purchase_request.approve",
        )
        foreign_type = WorkflowType.objects.exclude(pk=self.workflow_type.pk).first()
        foreign_template = WorkflowTemplate.objects.create(
            workflow_type=foreign_type,
            code="foreign-type",
            name="Other type",
            configuration={"steps": [], "transitions": []},
        )
        self.assertEqual(
            self.client.post(
                reverse("workflows:version_edit", args=[version.pk]),
                {"template": str(foreign_template.pk)},
            ).status_code,
            400,
        )
        # Removing active template availability cannot mutate the stored graph.
        template.is_active = False
        template.save()
        graph = configuration_payload(version)
        response = self.client.post(
            reverse("workflows:version_edit", args=[version.pk]),
            {"template": str(template.pk), "configuration": "{}"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(configuration_payload(version), graph)

    def test_complete_lifecycle_uses_existing_services_and_preserves_old_graph(self):
        response = self.client.post(
            reverse("workflows:definition_create"),
            {
                "workflow_type": str(self.workflow_type.pk),
                "code": "purchase-ui",
                "name": "گردش‌کار خرید",
                "scope": "{}",
            },
        )
        self.assertEqual(response.status_code, 302)
        version = WorkflowVersion.objects.get(organization=self.organization)
        self.assertEqual(WorkflowInstance.objects.count(), 0)
        edit = reverse("workflows:version_edit", args=[version.pk])
        self.assertEqual(
            self.client.post(
                edit, {"configuration": json.dumps(valid_configuration())}
            ).status_code,
            302,
        )
        self.assertEqual(self.action(version, "validate").status_code, 302)
        version.refresh_from_db()
        self.assertEqual(version.validation_report, [])
        self.assertIsNotNone(version.validated_at)
        self.assertEqual(self.action(version, "publish").status_code, 302)
        old_graph = configuration_payload(version)
        self.assertEqual(self.client.get(edit).status_code, 403)
        self.assertEqual(
            self.client.post(edit, {"configuration": "{}"}).status_code, 403
        )
        self.assertEqual(
            self.action(version, "new-draft", reason="اصلاح نسخه").status_code, 302
        )
        new = WorkflowVersion.objects.get(
            organization=self.organization, version_number=2
        )
        self.assertEqual(
            new.steps.count(), 0
        )  # Existing service creates an empty draft.
        edit_workflow_draft(
            actor=self.owner,
            organization=self.organization,
            version_id=new.pk,
            configuration=valid_configuration(),
        )
        self.assertEqual(self.action(new, "supersede").status_code, 400)
        self.assertEqual(
            self.action(new, "supersede", reason="نسخهٔ جایگزین").status_code, 302
        )
        version.refresh_from_db()
        new.refresh_from_db()
        self.assertEqual(version.status, "retired")
        self.assertEqual(new.status, "published")
        self.assertEqual(configuration_payload(version), old_graph)
        self.assertEqual(
            self.action(new, "retire", reason="پایان استفاده").status_code, 302
        )
        new.refresh_from_db()
        self.assertEqual(new.status, "retired")
        self.assertTrue(
            AuditEvent.objects.filter(
                action=AuditAction.WORKFLOW_VERSION_PUBLISHED
            ).exists()
        )
        self.assertEqual(WorkflowInstance.objects.count(), 0)

    def test_read_only_lifecycle_forms_and_navigation_do_not_mutate(self):
        version = self.draft()
        before = (
            WorkflowDefinition.objects.count(),
            WorkflowVersion.objects.count(),
            AuditEvent.objects.count(),
        )
        for route, args in [
            ("definition_list", []),
            ("version_detail", [version.pk]),
            ("version_edit", [version.pk]),
        ]:
            response = self.client.get(reverse("workflows:" + route, args=args))
            self.assertContains(response, 'data-workspace-id="WS-19"')
            self.assertContains(response, 'data-nav-id="NAV-039"')
            markup = response.content.decode()
            self.assertIn(
                "is-active",
                markup.split('data-nav-id="NAV-039"', 1)[1].split("</a>", 1)[0],
            )
            self.assertNotIn(
                "is-active",
                markup.split('data-nav-id="NAV-003"', 1)[1].split("</a>", 1)[0],
            )
        for action in ("validate", "publish", "retire", "supersede", "new-draft"):
            self.assertEqual(
                self.client.get(
                    reverse("workflows:version_action", args=[version.pk, action])
                ).status_code,
                200,
            )
        self.assertEqual(
            before,
            (
                WorkflowDefinition.objects.count(),
                WorkflowVersion.objects.count(),
                AuditEvent.objects.count(),
            ),
        )

    def test_permissions_are_independent_and_direct_actions_fail_closed(self):
        version = self.draft()
        actor, _ = self.reader()
        self.login(actor)
        response = self.client.get(
            reverse("workflows:version_detail", args=[version.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(
            response, reverse("workflows:version_edit", args=[version.pk])
        )
        for action in ("validate", "publish", "retire", "supersede", "new-draft"):
            self.assertEqual(
                self.action(version, action, reason="Denied").status_code, 403
            )
        self.assertEqual(
            self.client.post(reverse("workflows:definition_create"), {}).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(
                reverse("workflows:version_edit", args=[version.pk]), {}
            ).status_code,
            403,
        )
        for superuser in (False, True):
            denied, _ = self.reader(codes=(), superuser=superuser)
            self.login(denied)
            self.assertEqual(
                self.client.get(reverse("workflows:definition_list")).status_code, 403
            )
        PlatformRoleAssignment.objects.create(
            user=actor,
            role="platform_admin",
            assigned_by=self.owner,
            approved_by=self.owner,
            reason="Explicit synthetic platform authority",
        )
        self.login(actor)
        self.assertEqual(
            self.client.get(reverse("workflows:definition_list")).status_code, 200
        )
        # Platform authority did not expand the same reader's business capability.
        self.assertEqual(self.action(version, "publish").status_code, 403)

    def test_cross_tenant_objects_and_selected_context_do_not_expand_authority(self):
        foreign = self.draft(foreign=True)
        for target in (foreign.pk, uuid4()):
            for route in ("version_detail", "version_edit"):
                response = self.client.get(reverse("workflows:" + route, args=[target]))
                self.assertEqual(response.status_code, 404)
                self.assertNotContains(
                    response, foreign.definition.name, status_code=404
                )
            self.assertEqual(
                self.client.post(
                    reverse("workflows:version_action", args=[target, "publish"])
                ).status_code,
                404,
            )
        actor, membership = self.reader()
        membership.scope_grants.all().delete()
        self.login(actor)
        response = self.client.get(
            reverse("workflows:definition_list"),
            {"organization": str(self.other_organization.pk), "project": str(uuid4())},
        )
        self.assertEqual(response.status_code, 403)

    def test_invalid_configuration_and_failed_publication_preserve_draft(self):
        version = self.draft()
        edit = reverse("workflows:version_edit", args=[version.pk])
        self.assertEqual(
            self.client.post(edit, {"configuration": "["}).status_code, 400
        )
        bad = deepcopy(valid_configuration())
        bad["steps"][1]["configuration"] = {"python": "do_something()"}
        self.assertEqual(
            self.client.post(edit, {"configuration": json.dumps(bad)}).status_code, 400
        )
        self.assertEqual(version.steps.count(), 0)
        self.assertEqual(self.action(version, "publish").status_code, 400)
        version.refresh_from_db()
        self.assertEqual(version.status, "draft")
        self.assertEqual(self.action(version, "validate").status_code, 302)
        response = self.client.get(
            reverse("workflows:version_detail", args=[version.pk])
        )
        self.assertContains(response, "دقیقاً یک گام شروع")

    def test_invalid_nested_fields_and_routing_targets_have_neutral_errors(self):
        version = self.draft()
        edit = reverse("workflows:version_edit", args=[version.pk])
        invalid_key = valid_configuration()
        invalid_key["steps"][1]["key"] = "invalid key!"
        for transition in invalid_key["transitions"]:
            if transition["source"] == "decision":
                transition["source"] = "invalid key!"
            if transition["target"] == "decision":
                transition["target"] = "invalid key!"
        self.assertEqual(
            self.client.post(
                edit, {"configuration": json.dumps(invalid_key)}
            ).status_code,
            400,
        )
        foreign_membership = self.other_organization.memberships.get(user=self.other)
        for target in (foreign_membership.pk, uuid4()):
            config = valid_configuration()
            config["steps"][1]["routing"] = [
                {
                    "resolver_type": "explicit_membership",
                    "configuration": {"membership_id": str(target)},
                }
            ]
            response = self.client.post(edit, {"configuration": json.dumps(config)})
            self.assertContains(
                response, "هدف مسیریابی در این شرکت معتبر نیست.", status_code=400
            )
            self.assertNotContains(response, "متعلق به سازمان دیگری", status_code=400)

    def test_history_dates_are_jalali_and_untrusted_names_are_escaped(self):
        version = self.draft()
        WorkflowVersion.objects.filter(pk=version.pk).update(
            updated_at=datetime(2026, 1, 5, 12, tzinfo=UTC)
        )
        config = valid_configuration()
        config["steps"][0]["name"] = "<script>alert('test')</script>"
        edit_workflow_draft(
            actor=self.owner,
            organization=self.organization,
            version_id=version.pk,
            configuration=config,
        )
        WorkflowVersion.objects.filter(pk=version.pk).update(
            updated_at=datetime(2026, 1, 5, 12, tzinfo=UTC)
        )
        response = self.client.get(
            reverse("workflows:version_detail", args=[version.pk])
        )
        self.assertContains(response, "1404/10/15")
        self.assertContains(response, "&lt;script&gt;")
        self.assertNotContains(response, "<script>alert('test')</script>")

    def test_creation_validates_tenant_scope_and_neutral_duplicate_error(self):
        project = Project.objects.create(
            organization=self.other_organization, code="FOREIGN", name="Secret"
        )
        data = {
            "workflow_type": str(self.workflow_type.pk),
            "code": "scoped",
            "name": "Scoped",
        }
        for scope in (
            {"project_id": str(project.pk)},
            {"project_id": str(uuid4())},
            {"organization_id": str(self.other_organization.pk)},
            [],
        ):
            response = self.client.post(
                reverse("workflows:definition_create"),
                {**data, "scope": json.dumps(scope)},
            )
            self.assertEqual(response.status_code, 400)
            self.assertNotContains(response, "Secret", status_code=400)
        self.assertEqual(
            WorkflowDefinition.objects.filter(organization=self.organization).count(), 0
        )
        for expected in (302, 400):
            response = self.client.post(
                reverse("workflows:definition_create"), {**data, "scope": "{}"}
            )
            self.assertEqual(response.status_code, expected)

    def test_empty_csrf_and_inactive_tenant_states(self):
        response = self.client.get(reverse("workflows:definition_list"))
        self.assertContains(response, "تعریف گردش‌کاری در این شرکت ثبت نشده")
        version = self.draft()
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.owner)
        session = csrf_client.session
        session["active_organization_id"] = str(self.organization.pk)
        session.save()
        self.assertEqual(
            csrf_client.post(
                reverse("workflows:version_action", args=[version.pk, "publish"])
            ).status_code,
            403,
        )
        self.organization.status = "suspended"
        self.organization.save(update_fields=["status"])
        self.assertEqual(self.action(version, "publish").status_code, 403)
