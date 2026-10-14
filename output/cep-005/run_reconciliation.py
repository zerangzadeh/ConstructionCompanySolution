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
    'apps/projects/test_cep005_commitment_integration.py::CommitmentRootTests::test_reconciliation_missing_mismatch_duplicate_and_broken_lineage_is_read_only', 'apps/projects/test_cep005_commitment_integration.py::CommitmentRootTests::test_versions_adjustment_stale_replay_and_cancellation_release', '-q', '-s', '--reuse-db',
    '--junitxml=output/cep-005/reconciliation-test-results.xml',
]))
