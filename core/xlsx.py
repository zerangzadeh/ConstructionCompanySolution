"""Value-only XLSX downloads; callers supply already-authorized business data."""

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date, datetime
from io import BytesIO
from typing import Any
from zoneinfo import ZoneInfo

from django.http import FileResponse
from django.utils import timezone
from openpyxl import Workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

XLSX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@dataclass(frozen=True)
class Column:
    label: str
    value: str | Callable[[Any], Any]
    width: int = 24
    number_format: str | None = None

    def read(self, row: Any) -> Any:
        if callable(self.value):
            return self.value(row)
        for name in self.value.split("."):
            if row is None:
                return None
            row = getattr(row, name)
            if callable(row):
                row = row()
        return row


@dataclass(frozen=True)
class Sheet:
    title: str
    columns: tuple[Column, ...]
    rows: Iterable[Any]


def safe_filename(value: str) -> str:
    """Keep Persian business names, remove paths/control/header characters."""
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f\x7f]', "_", value)
    value = value.removesuffix(".xlsx").strip(" ._")[:140]
    return (value or "خروجی") + ".xlsx"


def workbook_file(sheets: Iterable[Sheet], *, timezone_name: str = "UTC") -> BytesIO:
    """Dates are Gregorian Excel dates; aware datetimes use the supplied tenant zone.

    Every string is explicitly stored as text, including formula-like strings,
    Excel error literals and numeric-looking document identifiers. No formulas,
    hyperlinks, macros or external links are generated.
    """
    workbook = Workbook()
    workbook.remove(workbook.active)
    for definition in sheets:
        title = re.sub(r"[\\/*?:\[\]\x00-\x1f]", "_", definition.title)
        title = title.strip(" '")[:31] or "داده‌ها"
        base_title = title
        suffix = 1
        while title.casefold() in {name.casefold() for name in workbook.sheetnames}:
            suffix += 1
            tail = f" ({suffix})"
            title = base_title[: 31 - len(tail)] + tail
        sheet = workbook.create_sheet(title)
        sheet.sheet_view.rightToLeft = True
        sheet.freeze_panes = "A2"
        sheet.row_dimensions[1].height = 36
        for index, column in enumerate(definition.columns, 1):
            cell = sheet.cell(1, index, column.label)
            cell.data_type = "s"
            cell.font = Font(name="Tahoma", bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="334155")
            cell.alignment = Alignment(horizontal="right", wrap_text=True)
            sheet.column_dimensions[get_column_letter(index)].width = column.width
        for row_number, row in enumerate(definition.rows, 2):
            for index, column in enumerate(definition.columns, 1):
                value = column.read(row)
                if isinstance(value, datetime) and timezone.is_aware(value):
                    value = timezone.localtime(value, ZoneInfo(timezone_name)).replace(
                        tzinfo=None
                    )
                if isinstance(value, str):
                    value = ILLEGAL_CHARACTERS_RE.sub("", value)[:32767]
                cell = sheet.cell(row_number, index, value)
                if isinstance(value, str):
                    cell.data_type = "s"
                    cell.number_format = "@"
                elif isinstance(value, datetime):
                    cell.number_format = "yyyy-mm-dd hh:mm:ss"
                elif isinstance(value, date):
                    cell.number_format = "yyyy-mm-dd"
                elif column.number_format:
                    cell.number_format = column.number_format
                cell.alignment = Alignment(horizontal="right", vertical="top")
        sheet.auto_filter.ref = sheet.dimensions
    if not workbook.worksheets:
        raise ValueError("At least one worksheet is required")
    stream = BytesIO()
    workbook.save(stream)
    workbook.close()
    stream.seek(0)
    return stream


def download(
    filename: str, sheets: Iterable[Sheet], *, timezone_name: str = "UTC"
) -> FileResponse:
    response = FileResponse(
        workbook_file(sheets, timezone_name=timezone_name),
        as_attachment=True,
        filename=safe_filename(filename),
        content_type=XLSX_CONTENT_TYPE,
    )
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response
