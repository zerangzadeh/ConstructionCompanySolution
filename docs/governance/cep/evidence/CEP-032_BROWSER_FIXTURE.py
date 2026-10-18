"""Reproduce CEP-032 browser checks using only the existing disposable test DB.

Run from the repository root after tests finish. No migrations, flush, production
access, or development policy changes. Stop the server after verification.
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

root = Path.cwd()
sys.path.insert(0, str(root))
load_dotenv(root / ".env")
source_database = os.environ["DB_NAME"]
assert not source_database.startswith("test_")
os.environ["DB_NAME"] = "test_" + source_database
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings.development"

import django

django.setup()

from django.core.management import execute_from_command_line
from django.db import connection

from apps.accounts.models import User
from apps.procurement.models import RequestForQuotation
from apps.procurement.rfq_services import (
    add_rfq_line,
    create_rfq,
    issue_rfq,
    submit_rfq_for_issue,
)
from apps.procurement.test_cep032_buyer_actions import BuyerActionTests

assert connection.settings_dict["NAME"] == "test_" + source_database
if "--serve-only" in sys.argv:
    execute_from_command_line(["manage.py", "runserver", "127.0.0.1:8001", "--noreload"])
    raise SystemExit(0)
if "--quote-source" in sys.argv:
    from datetime import timedelta
    from decimal import Decimal

    from django.utils import timezone

    source = RequestForQuotation.objects.get(rfq_number="RFQ-CUSTODY-001")
    actor = User.objects.get(username="admissibility-preparer")
    quote_rfq = create_rfq(
        organization=source.organization,
        actor=actor,
        project=source.project,
        purchase_request=source.purchase_request,
        rfq_number="CEP032-BROWSER-QUOTE",
        title="شاهد گردش پیشنهاد خریدار",
        closing_at=timezone.now() + timedelta(days=1),
        earliest_opening_at=timezone.now() + timedelta(days=1),
    )
    add_rfq_line(
        organization=source.organization,
        actor=actor,
        rfq=quote_rfq,
        purchase_request_item=source.purchase_request.items.get(),
        quantity=Decimal(2),
    )
    submit_rfq_for_issue(organization=source.organization, actor=actor, rfq=quote_rfq)
    issue_rfq(
        organization=source.organization,
        actor=actor,
        rfq=quote_rfq,
        suppliers=[source.versions.get().invitations.get().supplier],
        idempotency_key="browser-quote-issue",
    )
    print(
        f"BROWSER_QUOTE_RFQ=http://localhost:8001/procurement/rfqs/{quote_rfq.pk}/",
        flush=True,
    )
    raise SystemExit(0)
assert not User.objects.filter(username="admissibility-preparer").exists(), (
    "Existing fixture data must be inspected; this helper never flushes or deletes it."
)
fixture = BuyerActionTests()
fixture.setUp()
print(
    f"BROWSER_RFQ=http://127.0.0.1:8001/procurement/rfqs/{fixture.rfq.pk}/", flush=True
)
print(
    "Isolated test source ready; normal login uses synthetic fixture actors.",
    flush=True,
)
execute_from_command_line(["manage.py", "runserver", "127.0.0.1:8001", "--noreload"])
