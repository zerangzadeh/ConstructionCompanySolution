"""Source-package construction, not an author of statutory rules or current values."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import date
from typing import Any

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from apps.accounts.models import User
from apps.organizations.authorization import is_platform_admin
from apps.organizations.models import (
    PlatformPolicyVersion,
    PolicyReviewDisposition,
    PolicySourceBasis,
    PolicyVersionStatus,
)
from apps.organizations.policy_services import (
    publish_platform_policy_version,
    resolve_effective_platform_regulatory_policy,
)
from apps.organizations.policy_specs import (
    EMPLOYEE_INSURANCE_REGULATORY_POLICY_CODE,
    PAYROLL_TAX_REGULATORY_POLICY_CODE,
    get_platform_policy_spec,
    validate_policy_parameters,
)

from .models import StatutorySourcePackage

SOURCE_POLICY_CODES = frozenset(
    {PAYROLL_TAX_REGULATORY_POLICY_CODE, EMPLOYEE_INSURANCE_REGULATORY_POLICY_CODE}
)


def _digest(value: object) -> str:
    try:
        encoded = json.dumps(
            value,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
    except (TypeError, ValueError) as exc:
        raise ValidationError("ساختار بسته منبع معتبر نیست.") from exc
    return hashlib.sha256(encoded).hexdigest()


def _require_platform(actor: User) -> None:
    if not is_platform_admin(actor):
        raise PermissionDenied("مدیریت بسته منبع فقط با اختیار سیاست پلتفرم مجاز است.")


def _validate_payload(payload: object) -> None:
    if not isinstance(payload, dict) or set(payload) != {
        "schema_version",
        "ytd_treatment",
        "retroactivity",
        "evidence_references",
    }:
        raise ValidationError("فیلدهای بسته منبع باید صریح و نسخه‌دار باشند.")
    if type(payload["schema_version"]) is not int or payload["schema_version"] != 1:
        raise ValidationError("نسخه طرح بسته منبع پشتیبانی نمی‌شود.")
    for key in ("ytd_treatment", "retroactivity"):
        value = payload[key]
        # Retained source-authored descriptions/references, never executable rules.
        if not isinstance(value, dict) or set(value) != {
            "source_reference",
            "description",
        }:
            raise ValidationError("شرح و مرجع منبع برای رفتار قانونی الزامی است.")
        if any(
            not isinstance(item, str) or not item.strip() for item in value.values()
        ):
            raise ValidationError("شرح و مرجع منبع نباید خالی باشد.")
    refs = payload["evidence_references"]
    if (
        not isinstance(refs, list)
        or not refs
        or any(not isinstance(ref, str) or not ref.strip() for ref in refs)
    ):
        raise ValidationError("مدارک بسته منبع باید صریح باشند.")
    if any(
        payload[key]["source_reference"] not in refs
        for key in ("ytd_treatment", "retroactivity")
    ):
        raise ValidationError("مرجع رفتار باید در مدارک بسته منبع ثبت شده باشد.")


def _policy_snapshot(policy: PlatformPolicyVersion) -> dict[str, Any]:
    if policy.policy.code not in SOURCE_POLICY_CODES:
        raise ValidationError("این سیاست متعلق به بسته منبع قانونی حقوق نیست.")
    if policy.source_basis != PolicySourceBasis.EXTERNAL_AUTHORITY:
        raise ValidationError("منبع قانونی باید به مرجع بیرونی متکی باشد.")
    if (
        not policy.policy.is_active
        or policy.policy.tenant_selectable
        or policy.policy.sensitivity != "regulatory"
    ):
        raise ValidationError(
            "تعریف سیاست منبع قانونی باید فعال و مقرراتی پلتفرم باشد."
        )
    validate_policy_parameters(
        spec=get_platform_policy_spec(policy.policy.code), parameters=policy.parameters
    )
    sources = list(policy.sources.order_by("pk"))
    reviews = list(
        policy.review_evidence.filter(
            disposition=PolicyReviewDisposition.ACCEPTED
        ).order_by("pk")
    )
    if not sources or not reviews:
        raise ValidationError("بسته منبع بدون منبع و بررسی پذیرفته‌شده مجاز نیست.")
    governance = policy.parameters.get("statutory_governance")
    if governance:
        known_sources = {source.source_identifier for source in sources}
        if not {row["reference"] for row in governance["sources"]} <= known_sources:
            raise ValidationError(
                "Governed runtime sources must be retained policy sources."
            )
        adopted = policy.review_evidence.filter(
            evidence_reference=governance["review_reference"],
            disposition=PolicyReviewDisposition.ACCEPTED_WITH_CONDITIONS,
        ).first()
        if adopted is None:
            raise ValidationError(
                "The adopted Human conditional decision must be retained."
            )
    return {
        "id": str(policy.pk),
        "code": policy.policy.code,
        "version": policy.version,
        "effective_from": policy.effective_from.isoformat(),
        "effective_to": policy.effective_to.isoformat()
        if policy.effective_to
        else None,
        "source_basis": policy.source_basis,
        "parameters": deepcopy(policy.parameters),
        "sources": [
            {
                "id": str(source.pk),
                "issuer": source.issuer,
                "identifier": source.source_identifier,
                "version": source.version,
                "location": source.source_location,
                "applicability": source.applicability,
                "publication_date": source.publication_date.isoformat()
                if source.publication_date
                else None,
                "effective_from": source.effective_from.isoformat()
                if source.effective_from
                else None,
                "effective_to": source.effective_to.isoformat()
                if source.effective_to
                else None,
            }
            for source in sources
        ],
        "reviews": [
            {
                "id": str(review.pk),
                "evidence_reference": review.evidence_reference,
                "reviewer_identity": review.reviewer_identity,
                "qualification_summary": review.qualification_summary,
                "independence_statement": review.independence_statement,
                "review_scope": review.review_scope,
                "reviewed_on": review.reviewed_on.isoformat(),
            }
            for review in reviews
        ],
        **(
            {
                "adopted_review": {
                    "id": str(adopted.pk),
                    "evidence_reference": adopted.evidence_reference,
                    "disposition": adopted.disposition,
                    "conditions": adopted.conditions,
                    "review_scope": adopted.review_scope,
                    "review_sha256": governance["review_sha256"],
                }
            }
            if governance
            else {}
        ),
    }


def package_content(*, policy: PlatformPolicyVersion, payload: dict) -> dict:
    """Pure envelope construction against retained domain evidence (no activation)."""
    _validate_payload(payload)
    snapshot = _policy_snapshot(policy)
    known_references = {source["identifier"] for source in snapshot["sources"]} | {
        review["evidence_reference"] for review in snapshot["reviews"]
    }
    if "adopted_review" in snapshot:
        known_references.add(snapshot["adopted_review"]["evidence_reference"])
    if not set(payload["evidence_references"]) <= known_references:
        raise ValidationError("مدرک بسته باید به منبع یا بررسی ثبت‌شده متصل باشد.")
    return {**deepcopy(payload), "policy": snapshot}


def validate_source_package(package: StatutorySourcePackage) -> None:
    if not isinstance(package.content, dict) or "policy" not in package.content:
        raise ValidationError("بسته منبع فاقد سابقه سیاست است.")
    _validate_payload({k: v for k, v in package.content.items() if k != "policy"})
    if package.schema_version != package.content["schema_version"]:
        raise ValidationError("نسخه طرح بسته منبع هم‌خوان نیست.")
    if package.content_digest != _digest(package.content) or not package.reason.strip():
        raise ValidationError("اثر انگشت و دلیل بسته منبع الزامی و معتبر باشند.")
    if package.content != package_content(
        policy=package.policy_version,
        payload={k: v for k, v in package.content.items() if k != "policy"},
    ):
        raise ValidationError("مدارک یا پارامترهای سیاست با بسته منبع هم‌خوان نیست.")
    expected = package.policy_version.supersedes_id
    if expected:
        if (
            not package.supersedes_id
            or package.supersedes.policy_version_id != expected
        ):
            raise ValidationError("زنجیره جایگزینی بسته و سیاست هم‌خوان نیست.")
    elif package.supersedes_id:
        raise ValidationError("جایگزینی بسته بدون جایگزینی سیاست مجاز نیست.")


@transaction.atomic
def import_statutory_source_package(
    *, actor: User, policy_version: PlatformPolicyVersion, payload: dict, reason: str
) -> StatutorySourcePackage:
    _require_platform(actor)
    policy = (
        PlatformPolicyVersion.objects.select_for_update()
        .select_related("policy")
        .get(pk=policy_version.pk)
    )
    content = package_content(policy=policy, payload=payload)
    existing = StatutorySourcePackage.objects.filter(policy_version=policy).first()
    if existing:
        validate_source_package(existing)
        if existing.content != content:
            raise ValidationError("بسته قبلی تغییرپذیر نیست؛ نسخه سیاست جدید لازم است.")
        return existing
    if policy.status != PolicyVersionStatus.DRAFT:
        raise ValidationError("ورود بسته فقط پیش از انتشار سیاست مجاز است.")
    predecessor = None
    if policy.supersedes_id:
        predecessor = StatutorySourcePackage.objects.filter(
            policy_version_id=policy.supersedes_id
        ).first()
        if predecessor is None:
            raise ValidationError("بسته منبع نسخه پیشین موجود نیست.")
    return StatutorySourcePackage.objects.create(
        policy_version=policy,
        schema_version=payload["schema_version"],
        content=content,
        content_digest=_digest(content),
        supersedes=predecessor,
        imported_by=actor,
        reason=reason,
    )


@transaction.atomic
def activate_statutory_source_package(
    *, actor: User, package: StatutorySourcePackage, reason: str
) -> PlatformPolicyVersion:
    """Validate the envelope before the existing explicit policy publication."""
    _require_platform(actor)
    policy = PlatformPolicyVersion.objects.select_for_update().get(
        pk=package.policy_version_id
    )
    retained = StatutorySourcePackage.objects.get(pk=package.pk)
    retained.policy_version = policy
    validate_source_package(retained)
    return publish_platform_policy_version(
        actor=actor, policy_version=policy, reason=reason
    )


def resolve_statutory_source_package(
    *, code: str, consumer: str, on_date: date
) -> tuple[PlatformPolicyVersion, StatutorySourcePackage]:
    policy = resolve_effective_platform_regulatory_policy(
        code=code, consumer=consumer, on_date=on_date
    )
    package = StatutorySourcePackage.objects.filter(policy_version=policy).first()
    if package is None:
        raise ValidationError("بسته منبع نسخه‌دار و تأییدشده برای این سیاست وجود ندارد.")
    validate_source_package(package)
    return policy, package
