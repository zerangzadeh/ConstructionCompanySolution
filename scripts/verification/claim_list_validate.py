"""Run Claims verification in isolated PostgreSQL only."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
import django

django.setup()
import pytest
from django.db import connections

connections["default"].settings_dict["TEST"]["NAME"] = (
    "test_bonira_claim_list_clone_20261101"
)
raise SystemExit(
    pytest.main(sys.argv[1:] or ["apps/billing/test_claim_list.py", "--reuse-db", "-q"])
)
