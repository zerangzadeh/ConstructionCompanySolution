"""Populate deterministic development avatars for existing user accounts."""

import hashlib
import os
import struct
import zlib

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import User
from apps.accounts.services import update_personal_settings


def _png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    payload = chunk_type + data
    return (
        struct.pack(">I", len(data))
        + payload
        + struct.pack(">I", zlib.crc32(payload) & 0xFFFFFFFF)
    )


def _avatar_png(user: User, size: int = 256) -> bytes:
    """Create a small deterministic silhouette avatar without external packages."""

    digest = hashlib.sha256(str(user.pk).encode()).digest()
    accent = (45 + digest[0] % 85, 75 + digest[1] % 95, 125 + digest[2] % 95)
    background = tuple(min(channel + 135, 245) for channel in accent)
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
    help = "Populate deterministic user profile images in development."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--percentage", type=int, default=100)

    def handle(self, *args: object, **options: object) -> None:
        settings_module = os.environ.get("DJANGO_SETTINGS_MODULE", "")
        if settings_module != "config.settings.development" or not settings.DEBUG:
            raise CommandError(
                "This command is restricted to development settings with DEBUG=True."
            )

        percentage = options["percentage"]
        if not 0 <= percentage <= 100:
            raise CommandError("Percentage must be between 0 and 100.")

        total = User.objects.count()
        target = round(total * percentage / 100)
        populated = User.objects.exclude(profile_image="").count()
        needed = max(target - populated, 0)
        users = list(
            User.objects.filter(profile_image="").order_by("date_joined", "pk")[:needed]
        )

        for user in users:
            image = ContentFile(_avatar_png(user), name="demo-avatar.png")
            update_personal_settings(
                user=user,
                data={
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "email": user.email,
                    "phone_number": user.phone_number,
                    "profile_image": image,
                },
            )

        final_count = User.objects.exclude(profile_image="").count()
        self.stdout.write(
            self.style.SUCCESS(
                f"User profile images: {final_count}/{total} "
                f"(target {percentage}%, rounded to {target})."
            )
        )
