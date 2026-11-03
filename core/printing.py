"""Presentation contracts only; callers supply already authorized domain facts."""

from base64 import b64encode
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.utils import timezone

from apps.accounts.templatetags.erp_format import erp_number
from apps.organizations.models import Organization, validate_organization_logo
from core.jalali import format_jalali


@dataclass(frozen=True)
class Cell:
    text: object
    numeric: bool = False


def value(source: object, *, number: bool = False) -> Cell:
    """Reuse the UI's decimal/date presentation without calculating business facts."""
    if source is None or source == "":
        return Cell("—")
    if isinstance(source, (Decimal, int)) or number:
        return Cell(erp_number(source), numeric=True)
    return Cell(source)


def day(source: object) -> Cell:
    return Cell(format_jalali(source) if source else "—", numeric=True)


def moment(source: datetime | None, organization: Organization) -> Cell:
    local = (
        timezone.localtime(source, ZoneInfo(organization.settings.timezone))
        if source
        else None
    )
    return Cell(
        format_jalali(local.replace(tzinfo=None), include_time=True) if local else "—",
        numeric=True,
    )


@dataclass(frozen=True)
class Table:
    title: str
    headings: tuple[str, ...]
    rows: list[tuple[Cell, ...]]
    # Use a shared fixed width for descriptive first columns.
    wide_first: bool = False


@dataclass
class Document:
    title: str
    reference: object = ""
    metadata: list[tuple[str, Cell]] = field(default_factory=list)
    tables: list[Table] = field(default_factory=list)
    introduction: list[tuple[str, object]] = field(default_factory=list)
    notes: list[tuple[str, object]] = field(default_factory=list)
    totals: list[tuple[str, Cell]] = field(default_factory=list)
    approvals: list[tuple[str, Cell]] = field(default_factory=list)


def _logo(organization: Organization) -> str:
    """Embed the tenant's validated raster logo, never a user-controlled URL."""
    logo = organization.settings.logo
    if not logo:
        return ""
    try:
        with logo.open("rb") as stream:
            validate_organization_logo(stream)
            data = stream.read(2 * 1024 * 1024 + 1)
        if len(data) > 2 * 1024 * 1024:
            return ""
        mime = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
        }[Path(logo.name).suffix.lower()]
        return f"data:{mime};base64,{b64encode(data).decode('ascii')}"
    except (OSError, ValidationError, KeyError):
        return ""


def print_response(request: HttpRequest, document: Document) -> HttpResponse:
    """The source route owns all access checks; rendering performs no mutations."""
    query = request.GET.copy()
    query.pop("format", None)
    back_url = request.path + ("?" + query.urlencode() if query else "")
    response = render(
        request,
        "print/document.html",
        {
            "document": document,
            "print_organization": request.organization,
            "print_logo": _logo(request.organization),
            "print_back_url": back_url,
        },
    )
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    response["Content-Security-Policy"] = (
        "default-src 'none'; style-src 'self'; font-src 'self'; "
        "script-src 'self'; img-src data:; base-uri 'none'; "
        "form-action 'none'; frame-ancestors 'self'"
    )
    return response
