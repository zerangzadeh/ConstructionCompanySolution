"""Run scoped safety checks, restoring only missing code-owned test seed data."""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

import pytest


class RestoreSafetyTemplate:
    @pytest.fixture(scope="session", autouse=True)
    def restore_template(self, django_db_setup, django_db_blocker):
        from django.db import connection

        from apps.safety import workflow
        from apps.workflows.models import WorkflowTemplate, WorkflowType

        with django_db_blocker.unblock():
            if not connection.settings_dict["NAME"].startswith("test_"):
                raise RuntimeError("Seed restoration is restricted to test databases")
            WorkflowTemplate.objects.get_or_create(
                workflow_type=WorkflowType.objects.get(
                    code=workflow.WORKFLOW_TYPE_CODE
                ),
                code=workflow.TEMPLATE_CODE,
                defaults={
                    "name": workflow.TEMPLATE_CODE,
                    "configuration": workflow.COMPATIBILITY_CONFIGURATION,
                },
            )


raise SystemExit(
    pytest.main(
        [
            "apps/safety/test_context_choices.py",
            "apps/safety/tests.py",
            "apps/safety/test_cep079_hse_scope.py",
            "--reuse-db",
            "-q",
        ],
        plugins=[RestoreSafetyTemplate()],
    )
)
