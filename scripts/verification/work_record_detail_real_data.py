"""Read-only rendering against existing local records; no sessions saved."""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
import django

django.setup()
from collections import Counter

from django.contrib.sessions.backends.db import SessionStore
from django.db import connection, transaction
from django.test import RequestFactory
from django.urls import resolve, reverse

from apps.billing.models import ProgressRecord
from apps.billing.views import progress_detail
from apps.organizations.models import OrganizationMembership

results = Counter()
with transaction.atomic():
    with connection.cursor() as cursor:
        cursor.execute("SET TRANSACTION READ ONLY")
    records = list(
        ProgressRecord.objects.select_related(
            "organization", "created_by", "baseline", "baseline_item"
        ).all()
    )
    for state in ("verified", "submitted", "rejected", "draft"):
        record = next((r for r in records if r.status == state), None)
        if record is None:
            continue
        actor = record.created_by
        membership = OrganizationMembership.objects.filter(
            organization=record.organization, user=actor, status="active"
        ).first()
        if membership is None:
            continue
        path = reverse("billing:progress_detail", args=[record.pk])
        request = RequestFactory().get(path)
        request.user = actor
        request.organization = record.organization
        request.organization_membership = membership
        request.session = SessionStore()
        request.resolver_match = resolve(path)
        response = progress_detail(request, record_id=str(record.pk))
        assert response.status_code == 200
        html = response.content.decode()
        assert "کارکرد این ثبت" in html and "کارکرد تجمعی تا این ثبت" in html
        assert record.source_reference in html
        results[state] += 1
    results["available_records"] = len(records)
    results["historical_records_available"] = sum(
        r.baseline.version
        < max(
            s.baseline.version
            for s in records
            if s.baseline.contract_id == r.baseline.contract_id
        )
        for r in records
    )
print(dict(results))
