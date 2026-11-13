from django.test import TestCase

from apps.accounting.test_cep042_regression import explicit_fixture_authority
from apps.organizations.models import OrganizationRole
from apps.parties import tests as historical

class QualifiedPartyServices(historical.BusinessPartyServiceTests, TestCase):
    def setUp(self):
        super().setUp()
        for organization in (self.organization, self.other_organization):
            for membership in organization.memberships.all():
                role = OrganizationRole.objects.get(organization=None, code=membership.role)
                membership.role_definition = role
                membership.save(update_fields=['role_definition'])
                explicit_fixture_authority(membership, role)
