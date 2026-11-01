"""Estimate Create acceptance in installed Chrome on an isolated test database."""

import json
import os
import subprocess
from pathlib import Path

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.urls import reverse

from apps.billing import test_mvp03_browser as browser_fixture
from apps.billing.test_mvp03 import JourneyFixture
from apps.estimates.models import Estimate
from apps.projects.models import Project, ProjectPhase, ProjectSite


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class EstimateCreateReferenceBrowserTests(JourneyFixture, StaticLiveServerTestCase):
    def browser(self, actor, scenarios):
        self.login(actor)
        env = os.environ.copy()
        env["MVP02_SESSION"] = self.client.cookies["sessionid"].value
        env["MVP02_SCENARIOS"] = json.dumps(scenarios)
        root = Path(__file__).resolve().parents[2]
        result = subprocess.run(
            [
                "node",
                str(root / "scripts/verification/estimate_create_browser.mjs"),
                self.live_server_url,
                str(self.browser_evidence_directory),
                actor.username,
            ],
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=240,
            check=False,
        )
        self.assertEqual(result.returncode, 0, (result.stderr or result.stdout)[-3000:])
        results = json.loads(result.stdout)
        self.assertEqual(len(results), len(scenarios))
        (
            self.browser_evidence_directory / f"batch-{scenarios[0]['name']}.json"
        ).write_text(
            json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    _fixture_teardown = browser_fixture.ContractBillingBrowserTests._fixture_teardown
    browser_evidence_directory = (
        Path(__file__).resolve().parents[2] / "output/estimate-create-reference/browser"
    )

    def test_create_layout_validation_scope_and_context(self):
        self.make_fixture(persian=True)
        self.organization.name = "گروه عمران افق تهران"
        self.organization.save(update_fields=["name"])
        self.project.name = "بازسازی کارخانه نوآوران"
        self.project.save(update_fields=["name"])
        site = ProjectSite.objects.create(
            organization=self.organization,
            project=self.project,
            code="REF-S",
            name="کارگاه اصلی",
        )
        phase = ProjectPhase.objects.create(
            organization=self.organization,
            site=site,
            code="REF-PH",
            name="عملیات اجرایی فاز اول",
        )
        sibling = Project.objects.create(
            organization=self.organization, code="REF-OTHER", name="پروژه فعال دیگر"
        )
        create = reverse("estimates:create")
        selected = create
        self.login(self.owner)
        session = self.client.session
        session["active_project_id"] = str(self.project.pk)
        session.save()
        context = create + f"?project_id={self.project.pk}"
        common = {
            "status": 200,
            "screenshot": True,
            "noJsErrors": True,
            "noHttpErrors": True,
        }

        def check(expression, description):
            return {"inspect": expression, "description": description}

        scenarios = []
        for width in (1440, 1024, 390, 320):
            for direction in ("rtl", "ltr"):
                columns = 1 if width < 640 else 2
                scenarios.append(
                    {
                        **common,
                        "name": f"layout-{direction}-{width}",
                        "path": selected,
                        "width": width,
                        "mobile": width < 640,
                        "steps": [
                            check(
                                f"""(() => {{
                        const page=document.querySelector('.estimate-create-page');page.dir='{direction}';
                        const grid=page.querySelector('.erp-form-grid');
                        const names=['project','contract','phase','estimate_number','title','notes'];
                        const fields=Object.fromEntries(names.map(n=>[n,page.querySelector('[name='+n+']').closest('.erp-form-field')]));
                        const r=n=>fields[n].getBoundingClientRect();
                        return getComputedStyle(grid).gridTemplateColumns.split(' ').length==={columns}
                        && names.every(n=>!!fields[n]) && page.querySelectorAll('.erp-form-field').length===6
                        && r('project').width>={1.8 if width >= 640 else 0.99}*r('contract').width
                        && r('notes').width===r('project').width
                        && {"Math.abs(r('contract').top-r('phase').top)<2 && Math.abs(r('title').top-r('estimate_number').top)<2" if width >= 640 else "r('phase').top>r('contract').top && r('title').top>r('estimate_number').top"}
                        && document.querySelector('[name=project]').value==='{self.project.pk}'
                        && !document.querySelector('[name=contract]').value && !document.querySelector('[name=phase]').value
                        && document.documentElement.scrollWidth<=innerWidth+1;
                    }})()""",
                                "responsive grouping, selected project, empty optional controls and no overflow",
                            ),
                        ],
                    }
                )
        self.browser(self.owner, scenarios)
        self.browser(
            self.owner,
            [
                {
                    **common,
                    "name": "tab-navigation",
                    "path": selected,
                    "steps": [
                        check(
                            "(() => {document.querySelector('[name=estimate_number]').focus();return true;})()",
                            "focus number",
                        ),
                        {
                            "key": "Tab",
                            **check(
                                "document.activeElement.name==='title'",
                                "Tab reaches title",
                            ),
                        },
                        {
                            "key": "Tab",
                            **check(
                                "document.activeElement.name==='notes'",
                                "Tab reaches notes",
                            ),
                        },
                        {
                            "key": "Tab",
                            **check(
                                "document.activeElement.matches('.erp-form-footer button')",
                                "Tab reaches primary action",
                            ),
                        },
                        {
                            "key": "Tab",
                            **check(
                                "document.activeElement.matches('.erp-form-footer a')",
                                "Tab reaches cancel",
                            ),
                        },
                        {
                            "key": "Tab",
                            "shift": True,
                            **check(
                                "document.activeElement.matches('.erp-form-footer button')",
                                "Shift+Tab returns to primary action",
                            ),
                        },
                    ],
                }
            ],
        )
        self.browser(
            self.owner,
            [
                {
                    **common,
                    "name": "required-errors",
                    "path": create,
                    "mobile": True,
                    "steps": [
                        {
                            "fill": {"project": ""},
                            "waitMs": 400,
                            **check(
                                "document.querySelector('[name=project]').value===''",
                                "clear the preserved active-project default",
                            ),
                        },
                        {
                            "clickSelector": ".erp-form-footer button",
                            "afterPath": create,
                        },
                        check(
                            "['project','estimate_number','title'].every(n=>{const f=document.querySelector('[name='+n+']');return f.getAttribute('aria-invalid')==='true' && document.querySelector('#id_'+n+'-errors') && f.getAttribute('aria-describedby').includes('id_'+n+'-errors');}) && document.querySelectorAll('.erp-form-field--invalid').length===3",
                            "required errors adjacent and associated",
                        ),
                    ],
                },
                {
                    **common,
                    "name": "selected-optionals-keyboard",
                    "path": selected,
                    "steps": [
                        {
                            "searchChoice": {
                                "name": "contract",
                                "query": "F61-C",
                                "value": str(self.contract.pk),
                            },
                            "keyboard": True,
                        },
                        {
                            "searchChoice": {
                                "name": "phase",
                                "query": "عملیات",
                                "value": str(phase.pk),
                            },
                            "keyboard": True,
                        },
                        {
                            "fill": {
                                "estimate_number": "REF-LINKED",
                                "title": "برآورد عملیات اجرایی فاز اول",
                                "notes": "یادداشت نمونه",
                            },
                            "inspect": "true",
                            "description": "fill the existing fields without navigation",
                        },
                        check(
                            f"document.querySelector('[name=contract]').value==='{self.contract.pk}' && document.querySelector('[name=phase]').value==='{phase.pk}'",
                            "existing searchable choices selected by keyboard",
                        ),
                    ],
                },
                {
                    **common,
                    "name": "create-linked",
                    "path": selected,
                    "steps": [
                        {
                            "fill": {
                                "contract": str(self.contract.pk),
                                "phase": str(phase.pk),
                                "estimate_number": "REF-LINKED",
                                "title": "برآورد عملیات اجرایی فاز اول",
                                "notes": "یادداشت نمونه",
                            },
                            "clickSelector": ".erp-form-footer button",
                            "afterPrefix": "/estimates/",
                        },
                        check(
                            "!document.querySelector('.estimate-create-form')",
                            "existing create redirects to detail",
                        ),
                    ],
                },
                {
                    **common,
                    "name": "create-empty-optionals",
                    "path": context,
                    "mobile": True,
                    "steps": [
                        {
                            "fill": {
                                "estimate_number": "REF-EMPTY",
                                "title": "برآورد بدون قرارداد",
                            },
                            "clickSelector": ".erp-form-footer button",
                            "afterPrefix": "/estimates/",
                        },
                        check(
                            "!document.querySelector('.estimate-create-form')",
                            "optional relations remain optional",
                        ),
                    ],
                },
                {
                    **common,
                    "name": "duplicate-error",
                    "path": selected,
                    "steps": [
                        {
                            "fill": {
                                "estimate_number": "REF-LINKED",
                                "title": "عنوان تکراری",
                            },
                            "clickSelector": ".erp-form-footer button",
                            "afterPath": create,
                        },
                        check(
                            "!!document.querySelector('.estimate-create-form [role=alert]') && document.querySelector('[name=title]').value==='عنوان تکراری'",
                            "duplicate validation preserves submitted values",
                        ),
                    ],
                },
                {
                    **common,
                    "name": "cancel-context",
                    "path": context,
                    "mobile": True,
                    "steps": [
                        {
                            "clickSelector": ".erp-form-footer a",
                            "afterPath": reverse(
                                "projects:detail", args=[self.project.pk]
                            ),
                        }
                    ],
                },
            ],
        )
        linked = Estimate.objects.get(estimate_number="REF-LINKED")
        self.assertEqual(linked.contract, self.contract)
        self.assertEqual(linked.phase, phase)
        self.assertEqual(linked.notes, "یادداشت نمونه")
        empty = Estimate.objects.get(estimate_number="REF-EMPTY")
        self.assertIsNone(empty.contract)
        self.assertIsNone(empty.phase)
        self.assertEqual(empty.project, self.project)
        self.login(self.owner)
        session = self.client.session
        session["active_project_id"] = str(sibling.pk)
        session.save()
        before = dict(self.client.session)
        response = self.client.get(create)
        self.assertEqual(
            str(response.context["form"].initial["project"]), str(sibling.pk)
        )
        self.client.get(context)
        self.assertEqual(dict(self.client.session), before)
        # A form choice must never mutate global project context.
        self.browser(
            self.owner,
            [
                {
                    **common,
                    "name": "project-change-local",
                    "path": create,
                    "steps": [
                        {
                            "searchChoice": {
                                "name": "project",
                                "query": "نوآوران",
                                "value": str(self.project.pk),
                            },
                            "keyboard": True,
                        },
                        check(
                            f"document.querySelector('[name=project]').value==='{self.project.pk}'",
                            "project choice remains local",
                        ),
                        {
                            "clickSelector": ".erp-form-footer a",
                            "afterPath": reverse("estimates:list"),
                        },
                    ],
                }
            ],
        )
        self.assertEqual(dict(self.client.session), before)
        self.browser(
            self.member,
            [
                {
                    "name": f"restricted-{w}",
                    "path": create,
                    "status": 403,
                    "width": w,
                    "mobile": w < 640,
                    "screenshot": True,
                    "steps": [
                        check(
                            "!document.querySelector('.estimate-create-form')",
                            "restricted user cannot open create form",
                        )
                    ],
                }
                for w in (1440, 390)
            ],
        )
