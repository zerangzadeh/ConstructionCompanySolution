"""Production diagnostic contract, with private synthetic Linux storage."""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from django.test import SimpleTestCase

from core.production_operations import (
    ProductionOperationsHandler,
    ProductionOperationsSink,
    install_authentication_observer,
)


class ProductionOperationsTests(SimpleTestCase):
    def test_authentication_observer_never_retains_credentials(self):
        from django.contrib.auth.signals import user_login_failed

        with TemporaryDirectory() as directory:
            path = Path(directory)
            path.chmod(0o700)
            sink = ProductionOperationsSink(
                path, environment="production-equivalent-qualification"
            )
            install_authentication_observer(sink)
            try:
                user_login_failed.send(
                    sender=self.__class__,
                    credentials={"password": "never-retain-this"},
                    request=None,
                )
                data = next(path.iterdir()).read_text()
                self.assertEqual(json.loads(data)["signal"], "authentication.failed")
                self.assertNotIn("never-retain-this", data)
            finally:
                user_login_failed.disconnect(
                    dispatch_uid="bonira.production.authentication-observer"
                )

    def test_private_durable_receipt_and_explicit_retention(self):
        with TemporaryDirectory() as directory:
            path = Path(directory)
            path.chmod(0o700)
            sink = ProductionOperationsSink(
                path, environment="production-equivalent-qualification"
            )
            record = sink.write(signal="backup.failed", request_id=str(uuid4()))
            resumed = ProductionOperationsSink(
                path, environment="production-equivalent-qualification"
            )
            self.assertEqual(
                json.loads(next(resumed.directory.iterdir()).read_text()), record
            )
            self.assertEqual(
                datetime.fromisoformat(record["retain_until"])
                - datetime.fromisoformat(record["observed_at"]),
                timedelta(days=30),
            )
            with self.assertRaises(ValueError):
                sink.write(signal="payroll.financial.alert")
            path.chmod(0o755)
            with self.assertRaises(ValueError):
                sink.write(signal="backup.failed")

    def test_security_http_correlation_and_no_message_leak(self):
        with TemporaryDirectory() as directory:
            path = Path(directory)
            path.chmod(0o700)
            sink = ProductionOperationsSink(
                path, environment="production-equivalent-qualification"
            )
            handler = ProductionOperationsHandler(sink)
            record = logging.LogRecord(
                "bonira.request", 40, "secret/path", 1, "secret password", (), None
            )
            record.request_id = str(uuid4())
            for status in (401, 403, 503):
                record.status_code = status
                handler.emit(record)
            events = [json.loads(p.read_text()) for p in path.iterdir()]
            self.assertEqual(
                {e["signal"] for e in events if "signal" in e},
                {"authentication.failed", "authorization.denied", "http.server_error"},
            )
            self.assertTrue(all(e["request_id"] == record.request_id for e in events))
            self.assertNotIn("secret", json.dumps(events))
