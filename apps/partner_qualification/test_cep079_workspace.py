from django.template import Context, loader
from django.test import RequestFactory, TestCase

from apps.partner_qualification.views import workbench
from apps.procurement.tests import ProcurementFixtureMixin


class PartnerWorkspaceTenantTests(ProcurementFixtureMixin, TestCase):
    def test_workbench_uses_validated_request_organization(self):
        request = RequestFactory().get("/partners/")
        request.user = self.owner
        request.organization = self.organization
        self.assertFalse(hasattr(request, "active_organization"))
        response = workbench(request)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "صلاحیت و عملکرد همکاران")

    def test_partner_navigation_requires_its_existing_permission(self):
        template = loader.get_template("parties/_surface_navigation.html")
        for codes in (
            set(),
            {"parties.view"},
            {"partner.view"},
            {"parties.view", "partner.view"},
        ):
            with self.subTest(codes=codes):
                rendered = template.template.render(
                    Context({"business_permission_codes": codes})
                )
                self.assertEqual(
                    'href="/partners/"' in rendered, "partner.view" in codes
                )
