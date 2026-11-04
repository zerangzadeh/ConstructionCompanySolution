"""Transactional UI orchestration; source services retain evidence authority."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any
from uuid import UUID

from django.core.exceptions import PermissionDenied
from django.db import transaction

from apps.documents.evidence import (
    DENIED,
    EvidenceSource,
    eligible_versions,
    picker_source,
)
from apps.documents.models import Document

if TYPE_CHECKING:
    from apps.accounts.models import User
    from apps.organizations.models import Organization


@transaction.atomic
def register_evidence(
    *,
    user: User,
    organization: Organization,
    kind: str,
    source_id: UUID | str,
    values: Mapping[str, Any],
) -> EvidenceSource:
    source = picker_source(
        user=user, organization=organization, kind=kind, identifier=source_id
    )
    if kind not in {
        "safety",
        "quality",
        "contractual",
        "field_observation",
        "material",
    }:
        raise PermissionDenied(DENIED)
    # The existing material service pins the current version. Serialize with
    # version addition so the user's selected exact identity cannot drift.
    if kind == "material" and not (
        Document.objects.select_for_update()
        .filter(organization=organization, pk=values["version"].document_id)
        .exists()
    ):
        raise PermissionDenied(DENIED)
    ids = (
        [str(version.pk) for version in values.get("versions", [])]
        if kind in {"safety", "quality"}
        else [str(values["version"].pk)]
    )
    # Revalidate DMS and every linked context inside the registration transaction.
    allowed = eligible_versions(
        user=user, organization=organization, kind=kind, source=source
    )
    versions = list(allowed.filter(pk__in=ids))
    if len(versions) != len(set(ids)):
        raise PermissionDenied(DENIED)
    if kind in {"safety", "quality"}:
        if kind == "safety":
            from apps.safety.record_review import submit_safety_record

            submit_safety_record(
                organization=organization,
                actor=user,
                incident_id=str(source.target.pk),
                reason=values["reason"],
                document_version_ids=ids,
            )
        else:
            from apps.quality.record_review import submit_quality_record

            submit_quality_record(
                organization=organization,
                actor=user,
                issue_id=str(source.target.pk),
                reason=values["reason"],
                document_version_ids=ids,
            )
    elif kind == "contractual":
        from apps.contracts.contractual_services import add_contractual_evidence

        add_contractual_evidence(
            organization=organization,
            actor=user,
            record=source.target,
            label=values["label"],
            document_version=versions[0],
        )
    elif kind == "material":
        from apps.documents.services import add_document_link

        add_document_link(
            document=versions[0].document, actor=user, target=source.target
        )
    else:
        from apps.daily_reports.field_services import attach_field_evidence

        attach_field_evidence(
            organization=organization,
            actor=user,
            observation_id=str(source.target.pk),
            document_version_id=str(versions[0].pk),
            operation_key=values["operation_key"],
        )
    return source
