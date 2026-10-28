"""Narrow changed-scope Linux tests under secure Production configuration."""

import json
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import django
django.setup()
from django.conf import settings
from django.core.management import call_command
from django.test.runner import DiscoverRunner

OUT=Path('/evidence')
assert settings.SETTINGS_MODULE=='config.settings.production' and not settings.DEBUG
assert settings.DATABASES['default']['NAME']=='pe_gate11_20261028_tests'
assert settings.DATABASES['default']['OPTIONS']['sslmode']=='verify-full'
settings.DATABASES['default'].setdefault('TEST',{})['NAME']='test_pe_gate11_20261028_tests'
settings.PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher']
labels=[
 'apps.payroll.test_production_governance.ProductionEnvelopeTests',
 'apps.payroll.test_production_governance.ProductionStatutoryTests.test_production_tax_and_insurance_import_activate_and_calculate',
 'apps.payroll.test_cep069.AdoptedStatutoryTests',
 'tests.test_production_operations.ProductionOperationsTests',
 'tests.test_operations.OperationsTests',
 'apps.support.test_p9_s16_s20.SupportP9S16S20Tests.test_permission_catalog_default_deny_and_platform_role_is_not_tenant_access',
 'apps.support.test_p9_s16_s20.SupportP9S16S20Tests.test_support_access_sod_scope_expiry_revocation_and_audit',
 'apps.support.test_p9_s16_s20.SupportP9S16S20Tests.test_expired_access_and_stale_approval_fail_closed',
]
with (OUT/'FINAL_APP_TESTS.txt').open('w') as log,redirect_stdout(log),redirect_stderr(log):
 call_command('check',deploy=True,fail_level='WARNING')
 call_command('makemigrations',check=True,dry_run=True,verbosity=0)
 settings.SECURE_SSL_REDIRECT=False  # Test client only; deployment checks above use secure settings.
 failed=DiscoverRunner(verbosity=2,interactive=False,keepdb=True).run_tests(labels)
(OUT/'FINAL_APP_TESTS.json').write_text(json.dumps({'failed':failed,'labels':labels,'settings':'config.settings.production','base_debug':False,'legacy_development_scope_tests':'Explicit per-class overrides retained','production_envelope_activation':'Synthetic isolated TestCase database only','production':False},indent=2)+'\n')
assert failed==0
