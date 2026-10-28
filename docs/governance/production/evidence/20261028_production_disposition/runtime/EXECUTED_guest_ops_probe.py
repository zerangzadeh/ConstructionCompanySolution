"""Production diagnostic/access delta on a synthetic test database."""
import json
from contextlib import redirect_stderr,redirect_stdout
from pathlib import Path
import django
django.setup()
from django.conf import settings
from django.test.runner import DiscoverRunner
OUT=Path('/evidence')
assert settings.SETTINGS_MODULE=='config.settings.production' and not settings.DEBUG
settings.DATABASES['default'].setdefault('TEST',{})['NAME']='test_pe_gate11_20261028_tests'
settings.PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher']
settings.SECURE_SSL_REDIRECT=False
labels=['tests.test_production_operations.ProductionOperationsTests',
'apps.support.test_p9_s16_s20.SupportP9S16S20Tests.test_permission_catalog_default_deny_and_platform_role_is_not_tenant_access',
'apps.support.test_p9_s16_s20.SupportP9S16S20Tests.test_support_access_sod_scope_expiry_revocation_and_audit',
'apps.support.test_p9_s16_s20.SupportP9S16S20Tests.test_expired_access_and_stale_approval_fail_closed']
with (OUT/'OPS_ACCESS_TESTS.txt').open('w') as log,redirect_stdout(log),redirect_stderr(log):
 failed=DiscoverRunner(verbosity=2,interactive=False,keepdb=True).run_tests(labels)
(OUT/'OPS_ACCESS_TESTS.json').write_text(json.dumps({'failed':failed,'labels':labels,'production':False},indent=2)+'\n')
assert failed==0
