"""Run the bounded list checks in the existing isolated PostgreSQL test database."""
import os
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
import django
django.setup()
import pytest
from django.db import connections
from apps.contracts.test_filter_bar_browser import ContractFilterBrowserTests
from apps.contracts.test_reference_list_browser import ReferenceContractListBrowserTests

connections['default'].settings_dict['TEST']['NAME'] = 'test_bonira_mvp03_20261029'
ContractFilterBrowserTests.browser_evidence_directory = Path(__file__).parent / 'filter-regression'
ReferenceContractListBrowserTests.browser_evidence_directory = Path(__file__).parent / 'browser'
raise SystemExit(pytest.main([
    'apps/contracts/test_filter_bar.py',
    'apps/contracts/test_filter_bar_browser.py',
    'apps/contracts/test_reference_list_browser.py', '--reuse-db', '-q',
]))
