"""Small OpenSSL CMS adapter for governed encrypted base/WAL/file captures.

Operators supply pre-provisioned, disjoint private boundaries and public recipient
certificates. Private keys are used only by the separate recovery operator. No
credential contents, scheduler, purge or Production activation is provided here.
"""

from __future__ import annotations

import hashlib
import os
import stat
import subprocess
from pathlib import Path
from uuid import uuid4


class RecoveryError(Exception):
    """A capture/recovery control failed closed."""


def private_directory(path: Path) -> Path:
    if not path.is_absolute() or not path.is_dir():
        raise RecoveryError("Existing absolute private boundary required.")
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise RecoveryError("Linked storage boundaries are forbidden.")
    if os.name != "posix" or stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise RecoveryError("POSIX owner-only storage required.")
    return path.resolve()


def separate_boundaries(*paths: Path) -> None:
    resolved = [private_directory(p) for p in paths]
    for index, first in enumerate(resolved):
        for other in resolved[index + 1 :]:
            if first == other or first in other.parents or other in first.parents:
                raise RecoveryError(
                    "Active, archive and key boundaries must be disjoint."
                )


def file_hash(path: Path) -> str:
    if not path.is_file() or path.is_symlink():
        raise RecoveryError("Regular unlinked input required.")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _cms(arguments: list[str], output: Path) -> None:
    private_directory(output.parent)
    if output.exists() or output.is_symlink():
        raise RecoveryError("Recovery outputs must never overwrite existing data.")
    temporary = output.with_name("." + uuid4().hex + ".pending")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(descriptor)
    try:
        process = subprocess.run(
            ["openssl", "cms", *arguments, "-out", str(temporary)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        if process.returncode:
            raise RecoveryError("Protected capture authentication/decryption failed.")
        with temporary.open("rb") as stream:
            os.fsync(stream.fileno())
        # Atomic no-overwrite publication on the same private filesystem.
        os.link(temporary, output)
        descriptor = os.open(output.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    finally:
        temporary.unlink(missing_ok=True)


def encrypt(source: Path, output: Path, *, certificate: Path) -> dict:
    plaintext = file_hash(source)
    file_hash(certificate)
    _cms(
        [
            "-encrypt",
            "-binary",
            "-outform",
            "DER",
            "-aes-256-gcm",
            "-in",
            str(source),
            "-recip",
            str(certificate),
        ],
        output,
    )
    return {
        "sha256": file_hash(output),
        "plaintext_sha256": plaintext,
        "bytes": output.stat().st_size,
        "protection": "OpenSSL-CMS-AES-256-GCM",
    }


def decrypt(
    source: Path, output: Path, *, certificate: Path, private_key: Path
) -> None:
    file_hash(source)
    file_hash(certificate)
    file_hash(private_key)
    if stat.S_IMODE(private_key.stat().st_mode) & 0o077:
        raise RecoveryError("Recovery key custody must be owner-only.")
    separate_boundaries(source.parent, output.parent, private_key.parent)
    _cms(
        [
            "-decrypt",
            "-binary",
            "-inform",
            "DER",
            "-in",
            str(source),
            "-recip",
            str(certificate),
            "-inkey",
            str(private_key),
        ],
        output,
    )
