"""Canonical Daily Report submissions and their read-only presentation."""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from hashlib import sha256
from json import dumps
from types import SimpleNamespace
from uuid import UUID

from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.documents.models import DocumentLink, DocumentVersion
from apps.quality.models import QualityIssue
from apps.safety.models import SafetyIncident

from .models import (
    DailyActivity,
    DailyReportEquipmentEntry,
    DailyReportLaborEntry,
    DailyReportMaterialEntry,
    DelayEvent,
    DelayEventStatus,
)

HEADER_FIELDS = (
    "weather_conditions",
    "labor_count",
    "work_performed",
    "progress_summary",
    "issues_and_delays",
    "safety_notes",
    "quality_notes",
)
RETURN_POLICY = "independent_return_v1"


@dataclass(frozen=True)
class EntrySpec:
    model: type
    relation: str
    fields: tuple[str, ...]
    permission: str
    label: str


ENTRIES = {
    "labor": EntrySpec(
        DailyReportLaborEntry,
        "labor_entries",
        ("team_name", "worker_count", "hours_worked", "notes"),
        "daily_reports.add_labor",
        "نیروی انسانی",
    ),
    "equipment": EntrySpec(
        DailyReportEquipmentEntry,
        "equipment_entries",
        ("equipment_name", "hours_used", "notes"),
        "daily_reports.add_equipment",
        "تجهیزات",
    ),
    "materials": EntrySpec(
        DailyReportMaterialEntry,
        "material_entries",
        ("material", "material_name", "quantity", "unit_of_measure", "unit", "notes"),
        "daily_reports.add_material",
        "مصالح",
    ),
    "activities": EntrySpec(
        DailyActivity,
        "daily_activities",
        (
            "activity",
            "description",
            "quantity",
            "unit_of_measure",
            "progress_percent",
            "notes",
        ),
        "daily_reports.add_activity",
        "فعالیت‌ها",
    ),
    "delays": EntrySpec(
        DelayEvent,
        "delay_events",
        (
            "activity",
            "occurred_on",
            "category",
            "cause",
            "impact",
            "responsible_party",
            "duration_hours",
        ),
        "daily_reports.add_delay",
        "تأخیرها",
    ),
}


def json_value(value):
    if isinstance(value, (UUID, Decimal)):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if hasattr(value, "pk"):
        return str(value.pk)
    return value


def digest(payload):
    return sha256(
        dumps(
            payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")
        ).encode()
    ).hexdigest()


def entry_values(entry, spec):
    fields = [*spec.fields, "created_by_id"]
    if spec.model is DelayEvent:
        fields.append("status")
    return {
        entry._meta.get_field(name).attname: getattr(
            entry, entry._meta.get_field(name).attname
        )
        for name in fields
    }


def _entry_snapshot(entry, spec):
    if entry.organization_id != entry.report.organization_id:
        raise ValidationError("ردیف گزارش متعلق به این شرکت نیست.")
    for relation in ("activity", "material", "unit_of_measure"):
        linked = getattr(entry, relation, None)
        if linked and linked.organization_id != entry.organization_id:
            raise ValidationError("محدوده مرجع ردیف گزارش معتبر نیست.")
    data = {
        name: json_value(value) for name, value in entry_values(entry, spec).items()
    }
    data.update(id=str(entry.pk), created_at=json_value(entry.created_at))
    for name in ("material", "activity", "unit_of_measure"):
        obj = getattr(entry, name, None)
        if obj:
            data[name] = {
                "name": obj.name,
                "symbol": getattr(obj, "symbol", None),
                "code": getattr(obj, "code", None),
            }
    return data


def _source_references(report):
    if report.record_references.exclude(organization_id=report.organization_id).exists():
        raise ValidationError("ارجاع گزارش متعلق به این شرکت نیست.")
    result = {}
    for kind, model, field in (
        ("safety", SafetyIncident, "safety_incident_id"),
        ("quality", QualityIssue, "quality_issue_id"),
    ):
        origin = model.objects.filter(daily_report=report)
        linked = report.record_references.exclude(**{field: None}).values_list(
            field, flat=True
        )
        ids = set(origin.values_list("pk", flat=True)) | set(linked)
        records = model.objects.filter(
            pk__in=ids, organization_id=report.organization_id
        )
        if (
            records.count() != len(ids)
            or records.exclude(
                project_id=report.project_id,
                site_id=report.site_id,
                phase_id=report.phase_id,
            ).exists()
        ):
            raise ValidationError("محدوده ارجاع گزارش معتبر نیست.")
        number_field = "incident_number" if kind == "safety" else "issue_number"
        result[kind] = [
            {
                "id": str(record.pk),
                "number": getattr(record, number_field),
                "description": record.description,
                "status_label": record.get_status_display(),
                "project_id": str(record.project_id),
                "site_id": str(record.site_id),
                "phase_id": json_value(record.phase_id),
            }
            for record in records.order_by("pk")
        ]
    return result


def _document_pins(report, *, legacy):
    links = [
        *report.typed_document_links.select_related("document__current_version"),
        *DocumentLink.objects.filter(daily_report=report).select_related(
            "document__current_version"
        ),
    ]
    pins = {}
    for link in sorted(links, key=lambda row: (row._meta.label, str(row.pk))):
        doc = link.document
        version = doc.current_version
        if legacy:
            # Document-level links cannot establish which version existed at submission.
            raise ValidationError("نسخه سند در زمان ارسال قبلی قابل اثبات نیست.")
        if (
            link.organization_id != report.organization_id
            or doc.organization_id != report.organization_id
            or version is None
            or version.organization_id != report.organization_id
            or version.document_id != doc.pk
            or not version.sha256
            or not version.is_available
        ):
            raise ValidationError("نسخه معتبر برای سند مرتبط گزارش یافت نشد.")
        pin = pins.setdefault(
            str(doc.pk),
            {
                "document_id": str(doc.pk),
                "version_id": str(version.pk),
                "sha256": version.sha256,
                "title": doc.title,
                "links": [],
            },
        )
        pin["links"].append({"type": link._meta.label_lower, "id": str(link.pk)})
    return list(pins.values())


def _inherited_evidence(report):
    source = report.previous_revision
    verify_submission(source)
    snapshot = source.submission_snapshot
    for pin in snapshot["documents"]:
        version = DocumentVersion.objects.filter(
            pk=pin["version_id"],
            document_id=pin["document_id"],
            organization_id=report.organization_id,
            sha256=pin["sha256"],
        ).first()
        if version is None or not version.is_available:
            raise ValidationError("نسخه ثبت‌شده سند برای ارسال دوباره معتبر نیست.")
    for kind, model in (("safety", SafetyIncident), ("quality", QualityIssue)):
        ids = [reference["id"] for reference in snapshot["references"][kind]]
        if model.objects.filter(
            pk__in=ids,
            organization_id=report.organization_id,
            project_id=report.project_id,
            site_id=report.site_id,
            phase_id=report.phase_id,
        ).count() != len(ids):
            raise ValidationError("ارجاع ثبت‌شده برای ارسال دوباره معتبر نیست.")
    return snapshot["references"], snapshot["documents"]


def seal_submission(report, *, submitter, membership, creator_membership, legacy=False):
    """Build the seal while the caller holds the same parent lock as entry writers."""
    if report.previous_revision_id:
        references, documents = _inherited_evidence(report)
    else:
        references = _source_references(report)
        documents = _document_pins(report, legacy=legacy)
    payload = {
        "format": 1,
        "policy": RETURN_POLICY,
        "provenance": "legacy_capture" if legacy else "submission",
        "captured_at": timezone.now().isoformat(),
        "submitted_at": report.submitted_at.isoformat(),
        "revision_id": str(report.pk),
        "revision_number": report.revision_number,
        "previous_revision_id": json_value(report.previous_revision_id),
        "organization_id": str(report.organization_id),
        "project_id": str(report.project_id),
        "site_id": str(report.site_id),
        "phase_id": json_value(report.phase_id),
        "reporting_date": report.reporting_date.isoformat(),
        "author_id": str(report.created_by_id),
        "creator_membership_id": str(creator_membership.pk),
        "submitter_id": str(submitter.pk),
        "submitter_membership_id": str(membership.pk),
        "labels": {
            "project": report.project.name,
            "site": report.site.name,
            "phase": report.phase.name if report.phase_id else None,
        },
        "header": {name: getattr(report, name) for name in HEADER_FIELDS},
        "entries": {
            key: [
                _entry_snapshot(row, spec)
                for row in getattr(report, spec.relation).order_by("created_at", "pk")
            ]
            for key, spec in ENTRIES.items()
        },
        "references": references,
        "documents": documents,
    }
    report.submission_snapshot = payload
    report.submission_hash = digest(payload)


def return_enabled(report):
    return report.submission_snapshot.get("policy") == RETURN_POLICY


def verify_submission(report):
    if (
        not return_enabled(report)
        or report.submission_snapshot.get("revision_id") != str(report.pk)
        or report.submission_snapshot.get("organization_id")
        != str(report.organization_id)
        or digest(report.submission_snapshot) != report.submission_hash
    ):
        raise ValidationError("نسخه ثبت‌شده گزارش معتبر نیست.")


def frozen_label(report, name):
    return getattr(report, f"{name}_label")


def frozen_entries(report, kind):
    spec = ENTRIES[kind]
    if not report.submission_hash:
        return getattr(report, spec.relation).all()
    result = []
    for values in report.submission_snapshot["entries"][kind]:
        fields = dict(values)
        for field in spec.model._meta.concrete_fields:
            if (
                field.get_internal_type() == "DecimalField"
                and fields.get(field.name) is not None
            ):
                fields[field.name] = Decimal(fields[field.name])
        for name in ("material", "activity", "unit_of_measure"):
            fields[name] = SimpleNamespace(**fields[name]) if fields.get(name) else None
        if "occurred_on" in fields:
            fields["occurred_on"] = date.fromisoformat(fields["occurred_on"])
            status = fields["status"]
            fields["get_status_display"] = lambda status=status: (
                DelayEventStatus(status).label
            )
        result.append(SimpleNamespace(
            **fields, pk=fields["id"], report=report, organization_id=report.organization_id,
        ))
    return result
