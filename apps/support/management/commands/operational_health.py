"""Read-only dependency probes; no public endpoint or production acceptance."""

import json

from django.core.management.base import BaseCommand, CommandError

from core.operations import (
    ALERT_SIGNALS,
    dependency_signals,
    probe_cache,
    probe_database,
)


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
