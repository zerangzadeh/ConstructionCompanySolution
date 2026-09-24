"""Populate deterministic development avatars for existing employee records."""

import hashlib
import struct
import sys
import zlib

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError

from apps.organizations.models import MembershipStatus, OrganizationMembership
from apps.workforce.models import Employee
from apps.workforce.services import update_employee_profile_image


def _png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    payload = chunk_type + data
    return (
        struct.pack(">I", len(data))
        + payload
        + struct.pack(">I", zlib.crc32(payload) & 0xFFFFFFFF)
    )


def _avatar_png(employee: Employee, size: int = 256) -> bytes:
    """Create a small deterministic silhouette avatar without external packages."""

    digest = hashlib.sha256(str(employee.pk).encode()).digest()
    accent = (55 + digest[0] % 120, 65 + digest[1] % 110, 95 + digest[2] % 120)
    background = tuple(min(channel + 145, 245) for channel in accent)
    skin_tones = (
        (255, 224, 189),
        (241, 194, 125),
        (224, 172, 105),
        (198, 134, 66),
        (141, 85, 36),
    )
    skin = skin_tones[digest[3] % len(skin_tones)]
    rows = []
    for y in range(size):
        row = bytearray()
        for x in range(size):
            color = background
            if ((x - 128) / 94) ** 2 + ((y - 222) / 76) ** 2 <= 1:
                color = accent
            if (x - 128) ** 2 + (y - 91) ** 2 <= 44**2:
                color = skin
            row.extend(color)
        rows.append(b"\x00" + bytes(row))
    raw = b"".join(rows)
    header = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", header)
        + _png_chunk(b"IDAT", zlib.compress(raw, level=9))
        + _png_chunk(b"IEND", b"")
    )


class Command(BaseCommand):
    help = "Populate deterministic employee profile images in development."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--percentage", type=int, default=80)

    def handle(self, *args: object, **options: object) -> None:
        if not settings.DEBUG and "pytest" not in sys.modules:
            raise CommandError(
                "This command is restricted to development settings with DEBUG=True."
            )
        percentage = options["percentage"]
        if not 0 <= percentage <= 100:
            raise CommandError("Percentage must be between 0 and 100.")

        total = Employee.objects.count()
        target = round(total * percentage / 100)
        populated = Employee.objects.exclude(profile_image="").count()
        needed = max(target - populated, 0)
        employees = list(
            Employee.objects.filter(profile_image="")
            .select_related("organization")
            .order_by("organization_id", "employee_number", "pk")[:needed]
        )
        owners = {
            membership.organization_id: membership.user
            for membership in OrganizationMembership.objects.filter(
                organization_id__in={
                    employee.organization_id for employee in employees
                },
                status=MembershipStatus.ACTIVE,
                role_definition__is_owner=True,
                user__is_active=True,
            )
            .select_related("user")
            .order_by("organization_id", "created_at")
        }
        missing_owner_organizations = {
            employee.organization_id
            for employee in employees
            if employee.organization_id not in owners
        }
        if missing_owner_organizations:
            raise CommandError(
                "Every selected employee organization must have an active owner."
            )

        for employee in employees:
            image = ContentFile(_avatar_png(employee), name="demo-avatar.png")
            update_employee_profile_image(
                organization=employee.organization,
                actor=owners[employee.organization_id],
                employee=employee,
                data={"profile_image": image},
            )

        final_count = Employee.objects.exclude(profile_image="").count()
        self.stdout.write(
            self.style.SUCCESS(
                f"Employee profile images: {final_count}/{total} "
                f"(target {percentage}%, rounded to {target})."
            )
        )
