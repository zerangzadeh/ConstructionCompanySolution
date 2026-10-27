"""Isolated operational plumbing checks, without external sinks or business DB."""

import io
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import SimpleTestCase, TestCase

from apps.support.management.commands import operational_health
from core.operations import (
    DevelopmentOperationsHandler,
    DevelopmentOperationsSink,
    LocalOperationsAdapter,
    dependency_signals,
    request_failure_signal,
)


class OperationsTests(SimpleTestCase):
    def test_durable_local_receipt_survives_restart_with_thirty_day_retention(self):
        with TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            sink = DevelopmentOperationsSink(root)
            receipt = sink.write(signal="database.unreachable")
            self.assertEqual(
                datetime.fromisoformat(receipt["retain_until"])
                - datetime.fromisoformat(receipt["observed_at"]),
                timedelta(days=30),
            )
            resumed = DevelopmentOperationsSink(root)
            self.assertEqual(
                json.loads(next(resumed.directory.glob("*.json")).read_text()),
                receipt,
            )
            with self.assertRaises(ValueError):
                sink.write(signal="unregistered.financial.failure")

    def test_correlated_http_alert_has_no_payload_and_delivery_failure_propagates(self):
        with TemporaryDirectory() as directory:
            sink = DevelopmentOperationsSink(Path(directory).resolve())
            handler = DevelopmentOperationsHandler(sink)
            record = logging.LogRecord(
                "bonira.request", 40, "secret", 1, "secret", (), None
            )
            record.status_code = 503
            record.request_id = "e741fb0f-ae54-4748-947b-e024a1ae2eae"
            handler.emit(record)
            records = [json.loads(p.read_text()) for p in sink.directory.glob("*.json")]
            self.assertEqual(len(records), 2)
            self.assertTrue(all(r["request_id"] == record.request_id for r in records))
            for receipt in records:
                observed = receipt.get("observed_at", receipt.get("timestamp"))
                self.assertGreaterEqual(
                    datetime.fromisoformat(receipt["retain_until"])
                    - datetime.fromisoformat(observed),
                    timedelta(days=30),
                )
            self.assertNotIn("secret", json.dumps(records))
            with (
                patch("core.operations.os.fsync", side_effect=OSError("disk")),
                self.assertRaises(OSError),
            ):
                handler.emit(record)

    def test_dependency_failure_is_sanitized_and_other_probe_runs(self):
        called = []

        def broken():
            raise OSError("secret-database-credential")

        result = dependency_signals(database=broken, cache=lambda: called.append(True))
        self.assertEqual(result, ["database.unreachable", "cache.reachable"])
        self.assertEqual(called, [True])
        self.assertNotIn("secret", json.dumps(result))

    def test_health_command_exit_and_json_never_certify_readiness(self):
        for failed in (False, True):
            stream = io.StringIO()
            with (
                patch.object(
                    operational_health,
                    "probe_database",
                    side_effect=OSError("secret") if failed else None,
                ),
                patch.object(operational_health, "probe_cache"),
            ):
                if failed:
                    with self.assertRaises(CommandError):
                        call_command("operational_health", stdout=stream)
                else:
                    call_command("operational_health", stdout=stream)
            record = json.loads(stream.getvalue())
            self.assertEqual(record["production_readiness"], "NOT_VALIDATED")
            self.assertNotIn("secret", stream.getvalue())

    def test_cache_probe_only_reads_a_fresh_namespaced_key(self):
        with patch.object(operational_health, "cache") as cache:
            operational_health.probe_cache()
        cache.get.assert_called_once()
        self.assertTrue(
            cache.get.call_args.args[0].startswith("bonira-operational-probe:")
        )
        cache.set.assert_not_called()
        cache.delete.assert_not_called()

    def test_database_probe_is_read_only_and_result_checked(self):
        with (
            patch.object(operational_health, "transaction") as transaction,
            patch.object(operational_health, "connection") as connection,
        ):
            cursor = connection.cursor.return_value.__enter__.return_value
            cursor.fetchone.return_value = (1,)
            operational_health.probe_database()
            transaction.atomic.assert_called_once()
            self.assertEqual(
                [c.args[0] for c in cursor.execute.call_args_list],
                ["SET TRANSACTION READ ONLY", "SELECT 1"],
            )
            cursor.fetchone.return_value = (0,)
            with self.assertRaises(ValueError):
                operational_health.probe_database()

    def test_local_failure_alert_delivery_and_no_payload_copy(self):
        with LocalOperationsAdapter() as adapter:
            for raw, expected in (
                (
                    {
                        "event": "http.response",
                        "status_code": 503,
                        "password": "secret",
                    },
                    "http.server_error",
                ),
                (
                    {"event": "telemetry.delivery_failed", "message": "secret"},
                    "telemetry.delivery_failed",
                ),
            ):
                signal = request_failure_signal(raw)
                self.assertEqual(signal, expected)
                self.assertTrue(adapter.emit(signal)["alert"])
            self.assertFalse(adapter.emit("database.reachable")["alert"])
            files = list(adapter.directory.glob("*.json"))
            self.assertEqual(len(files), 3)
            self.assertTrue(all("secret" not in p.read_text() for p in files))
            with self.assertRaises(ValueError):
                adapter.emit("unapproved.business.failure")
        self.assertFalse(adapter.directory.exists())

    def test_request_alert_rules_do_not_invent_thresholds(self):
        for code in (200, 403, 499, 600, "503", True):
            self.assertIsNone(
                request_failure_signal({"event": "http.response", "status_code": code})
            )

    def test_retention_plans_then_removes_only_owned_old_diagnostics(self):
        with LocalOperationsAdapter() as adapter:
            with patch("core.operations.datetime") as clock:
                clock.now.return_value = datetime.now(UTC) - timedelta(days=2)
                adapter.emit("database.unreachable")
            cutoff = datetime.now(UTC) - timedelta(days=1)
            adapter.emit("database.reachable")
            unrelated = adapter.directory / "audit.json"
            unrelated.write_text("preserve")
            selected = adapter.retain(cutoff=cutoff)
            self.assertEqual(len(selected), 1)
            self.assertTrue((adapter.directory / selected[0]).exists())
            self.assertEqual(adapter.retain(cutoff=cutoff, execute=True), selected)
            self.assertEqual(len(list(adapter.directory.glob("*.json"))), 2)
            self.assertEqual(unrelated.read_text(), "preserve")
            for invalid in (
                datetime.now(UTC).replace(tzinfo=None),
                datetime.now(UTC) + timedelta(days=1),
            ):
                with self.assertRaises(ValueError):
                    adapter.retain(cutoff=invalid, execute=True)


class OperationsDependencyIntegrationTests(TestCase):
    def test_command_reads_isolated_test_database_and_cache(self):
        self.assertTrue(connection.settings_dict["NAME"].startswith("test_"))

        def run_probe():
            # A fresh thread has no TestCase transaction: exercise the command's
            # own read-only transaction against pytest's isolated test database.
            try:
                stream = io.StringIO()
                call_command("operational_health", stdout=stream)
                return json.loads(stream.getvalue())
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=1) as executor:
            record = executor.submit(run_probe).result(timeout=30)
        self.assertEqual(record["signals"], ["database.reachable", "cache.reachable"])
        self.assertEqual(record["production_readiness"], "NOT_VALIDATED")
