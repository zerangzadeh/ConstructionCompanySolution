"""Bounded synthetic screenshots for tenant workflow administration."""

import json
import os
import subprocess
from pathlib import Path
from unittest import skipUnless

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.urls import reverse

from apps.accounting.test_cep042_regression import explicit_fixture_authority
from apps.organizations.models import (
    Organization,
    OrganizationRole,
    OrganizationSettings,
)

from .models import WorkflowTemplate
from .services import (
    edit_workflow_draft,
    publish_workflow_version,
    validate_workflow_draft,
)
from .test_cep046_administration import AdministrationFixture
from .tests import valid_configuration


@skipUnless(
    os.getenv("BONIRA_CEP046_SCREENSHOTS"), "Explicit local screenshot run only"
)
class AdministrationBrowserTests(AdministrationFixture, StaticLiveServerTestCase):
    def setUp(self):
        super().setUp()
        self.workflow_type.name = "تأیید درخواست خرید"
        self.workflow_type.save(update_fields=["name"])
        WorkflowTemplate.objects.create(
            workflow_type=self.workflow_type,
            code="synthetic-ui-starter",
            name="الگوی آزمایشی تأیید خرید",
            configuration=valid_configuration(),
        )

    def organization_factory(self, *, owner, name, slug):
        # Explicit empty synthetic tenant. Production organization creation seeds
        # compatibility workflows on_commit; those services are not changed here.
        organization = Organization.objects.create(
            name=name, slug=slug, created_by=owner, updated_by=owner
        )
        OrganizationSettings.objects.create(organization=organization)
        role = OrganizationRole.objects.get(code="company_owner")
        membership = organization.memberships.create(
            user=owner, role_definition=role, role=role.code, status="active"
        )
        explicit_fixture_authority(membership, role)
        return organization

    def probe(self, cases):
        root = Path(__file__).resolve().parents[2]
        evidence = root / "docs/governance/cep/evidence"
        result = subprocess.run(
            [
                "node",
                str(evidence / "CEP-046_BROWSER_PROBE.mjs"),
                self.live_server_url,
                json.dumps(cases),
                str(evidence / "CEP-046_SCREENSHOTS"),
            ],
            env={
                **os.environ,
                "CEP046_TEST_SESSION": self.client.cookies["sessionid"].value,
            },
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=90,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-2500:])
        return json.loads(result.stdout)

    def test_synthetic_admin_surfaces_history_error_mobile_and_denied(self):
        def case(name, route, *args, status=200, mobile=False):
            return {
                "name": name,
                "path": reverse("workflows:" + route, args=args),
                "workspace": "WS-19" if status == 200 else "",
                "status": status,
                "mobile": mobile,
            }

        observations = self.probe(
            [
                case("empty-list", "definition_list"),
                case("definition-create", "definition_create"),
            ]
        )
        version = self.draft()
        kwargs = {
            "actor": self.owner,
            "organization": self.organization,
            "version_id": version.pk,
        }
        validate_workflow_draft(**kwargs)
        observations += self.probe(
            [case("validation-errors", "version_detail", version.pk)]
        )
        edit_workflow_draft(**kwargs, configuration=valid_configuration())
        observations += self.probe([case("draft-editor", "version_edit", version.pk)])
        publish_workflow_version(**kwargs)
        observations += self.probe(
            [
                case("published-history", "version_detail", version.pk),
                case("mobile-list", "definition_list", mobile=True),
            ]
        )
        foreign = self.draft(foreign=True)
        observations += self.probe(
            [case("foreign-object", "version_detail", foreign.pk, status=404)]
        )
        denied, _ = self.reader(codes=())
        self.login(denied)
        observations += self.probe(
            [case("unauthorized-list", "definition_list", status=403)]
        )
        root = Path(__file__).resolve().parents[2]
        (
            root / "docs/governance/cep/evidence/CEP-046_BROWSER_OBSERVATIONS.json"
        ).write_text(
            json.dumps(
                {
                    "environment": "Isolated synthetic StaticLiveServer / Chrome; no production data",
                    "observations": observations,
                    "runtime_certification": False,
                },
                indent=2,
            )
            + "\n",
            "utf-8",
        )
