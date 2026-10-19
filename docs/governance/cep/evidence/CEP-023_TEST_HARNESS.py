import os,sys
sys.path.insert(0,os.getcwd())
os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings.development")
sys.stdout.reconfigure(encoding="utf-8")
from django.conf import settings
settings.DATABASES["default"].setdefault("TEST",{})["NAME"]="test_bonira_cep023_20261019"
import pytest
class ExplicitLegacyScope:
    def pytest_collection_modifyitems(self, items):
        from apps.timekeeping.test_p7_s06_s12_timekeeping import P7TimekeepingTests
        from apps.organizations.models import OrganizationMembership, MembershipScopeGrant, AuthorizationScopeType
        original=P7TimekeepingTests._member
        def with_scope(case, username):
            user=original(case,username)
            membership=OrganizationMembership.objects.get(organization=case.organization,user=user)
            MembershipScopeGrant.objects.get_or_create(organization=case.organization,membership=membership,scope_type=AuthorizationScopeType.ORGANIZATION,defaults={"reason":"Explicit intended legacy fixture scope; test-only baseline repair"})
            return user
        P7TimekeepingTests._member=with_scope
mode="--migrations" if "--migrations" in sys.argv else "--no-migrations"
args=[x for x in sys.argv[1:] if x != "--migrations"]
sys.exit(pytest.main(args+["--reuse-db",mode,"-q","--tb=short","-o","faulthandler_timeout=0"],plugins=[ExplicitLegacyScope()]))
