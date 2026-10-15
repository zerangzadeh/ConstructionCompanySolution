import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

from django.conf import settings

settings.DATABASES["default"].setdefault("TEST", {})["NAME"] = (
    "test_cep009_validation_20261015_71e4"
)

import pytest

raise SystemExit(
    pytest.main(
        [
            "apps/inventory/test_cep009.py::InventoryBalanceQueryTests::test_warehouse_locks_follow_uuid_order_for_either_direction",
            "apps/inventory/test_p8_s05_s11.py::InventoryCustodyServiceTests::test_two_sided_transfer_conserves_quantity_and_is_retry_safe",
            "-q",
            "--reuse-db",
            "--junitxml=output/cep-009/validation-recheck-results.xml",
        ]
    )
)
