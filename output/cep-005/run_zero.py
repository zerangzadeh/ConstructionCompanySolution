import os
import sys
from pathlib import Path

# Evidence runner: always a separate, named non-production test database.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
from django.conf import settings
settings.DATABASES['default'].setdefault('TEST', {})['NAME'] = 'test_cep005_20261014'
import pytest
raise SystemExit(pytest.main([
    'apps/projects/test_cep005_commitment_integration.py::CommitmentRootTests::test_zero_result_successor_retains_version_lineage', '-q', '-s', '--reuse-db',
    '--junitxml=output/cep-005/zero-test-results.xml',
]))
