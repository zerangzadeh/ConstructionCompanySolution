"""Read-only dependency probes; no public endpoint or production acceptance."""

import json
from uuid import uuid4

from django.core.cache import cache
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from core.operations import ALERT_SIGNALS, dependency_signals


def probe_database() -> None:
    with transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("SET TRANSACTION READ ONLY")
        cursor.execute("SELECT 1")
        if cursor.fetchone() != (1,):
            raise ValueError("Unexpected database probe result.")


def probe_cache() -> None:
    # Read only; never overwrite or evict a business/session cache key.
    cache.get(f"bonira-operational-probe:{uuid4()}")


class Command(BaseCommand):
    help = "Read-only database/cache reachability, without readiness certification."
    requires_system_checks = ()

    def handle(self, *args, **options):
        signals = dependency_signals(database=probe_database, cache=probe_cache)
        self.stdout.write(
            json.dumps(
                {
                    "signals": signals,
                    "production_readiness": "NOT_VALIDATED",
                    "scope": "database-and-cache-reachability-only",
                }
            )
        )
        if any(signal in ALERT_SIGNALS for signal in signals):
            raise CommandError("Dependency probe failed; inspect sanitized signals.")
