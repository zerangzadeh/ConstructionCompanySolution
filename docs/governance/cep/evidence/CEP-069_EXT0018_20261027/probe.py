"""Inspect only loopback Development, with SQL-enforced read-only access."""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(OUT.parents[4]))
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings.development"
import django

django.setup()
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.db.migrations.executor import MigrationExecutor

from apps.organizations.models import PlatformPolicyVersion, PolicyReviewEvidence
from apps.payroll.models import StatutorySourcePackage
from apps.payroll.source_package_services import resolve_statutory_source_package

assert settings.DEBUG and connection.vendor == "postgresql"
assert connection.settings_dict["HOST"] in {"localhost", "127.0.0.1", "::1"}
codes = {
    "payroll-tax-regulatory": "payroll.statutory_tax.calculate",
    "employee-insurance-regulatory": "payroll.employee_insurance.calculate",
}
with transaction.atomic():
    with connection.cursor() as cursor:
        cursor.execute("SET TRANSACTION READ ONLY")
        cursor.execute("SHOW transaction_read_only")
        assert cursor.fetchone()[0] == "on"
        cursor.execute("SHOW server_version")
        server_version = cursor.fetchone()[0]
    versions = PlatformPolicyVersion.objects.filter(policy__code__in=codes)
    executor = MigrationExecutor(connection)
    result = {
        "at": datetime.now(timezone.utc).isoformat(),
        "environment": "LOOPBACK_DEVELOPMENT_SQL_READ_ONLY",
        "postgresql": server_version,
        "source_packages": StatutorySourcePackage.objects.count(),
        "statutory_versions": versions.count(),
        "published_versions": versions.filter(status="published").count(),
        "accepted_reviews": PolicyReviewEvidence.objects.filter(
            policy_version__in=versions, disposition="accepted"
        ).count(),
        "unapplied_migrations": [
            str(m) for m in executor.migration_plan(executor.loader.graph.leaf_nodes())
        ],
        "missing_source_resolution": [],
        "production_access": "NOT_EXECUTED",
    }
    from datetime import date

    for code, consumer in codes.items():
        for cutoff in (date(2025, 10, 27), date(2026, 10, 27), date(2027, 10, 27)):
            try:
                resolve_statutory_source_package(
                    code=code, consumer=consumer, on_date=cutoff
                )
            except ValidationError:
                result["missing_source_resolution"].append(
                    {
                        "code": code,
                        "on_date": str(cutoff),
                        "result": "FAIL_CLOSED_VALIDATION_ERROR",
                    }
                )
            else:
                result["missing_source_resolution"].append(
                    {
                        "code": code,
                        "on_date": str(cutoff),
                        "result": "RESOLVED_REQUIRES_QUALIFICATION",
                    }
                )
(OUT / "DEVELOPMENT.json").write_text(
    json.dumps(result, indent=2) + "\n", encoding="utf-8"
)
print(json.dumps(result))
