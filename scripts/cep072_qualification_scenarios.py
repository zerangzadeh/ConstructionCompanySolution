"""Executable EXT-0022 scenario, isolated test PostgreSQL and loopback HTTP only.

Run explicitly with pytest and BONIRA_OPERATIONS_EVIDENCE set to a fresh evidence
directory. This is a scenario driver, never a product URL configuration.
"""

import hashlib
import http.client
import io
import json
import os
import socket
import subprocess
import sys
import time
from contextlib import redirect_stderr
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Event, Thread
from uuid import uuid4
from wsgiref.simple_server import WSGIRequestHandler, make_server

from django.core.exceptions import PermissionDenied
from django.core.handlers.wsgi import WSGIHandler
from django.db import connection
from django.http import HttpResponse
from django.test import TestCase, override_settings
from django.urls import path

from apps.audit.models import AuditEvent
from apps.support import test_p9_s16_s20 as support_fixture
from apps.support.models import SupportAccessRequest
from apps.support.services import confirm_access, request_access, validate_access
from core.operations import DevelopmentOperationsSink
from scripts.cep070_recovery_controls import verify_private_tree
from scripts.cep072_operations_runtime import activate, provision_sink

FAILURE = Event()


def scenario_response(request):
    return HttpResponse("qualification", status=503 if FAILURE.is_set() else 200)


urlpatterns = [path("qualification/", scenario_response, name="qualification")]


class QuietHandler(WSGIRequestHandler):
    def log_message(self, *args):
        pass


class OperationsQualification(TestCase):
    setUp = support_fixture.SupportP9S16S20Tests.setUp
    _governed_access_fixture = (
        support_fixture.SupportP9S16S20Tests._governed_access_fixture
    )

    def test_executed_operational_scenario(self):
        self.assertTrue(connection.settings_dict["NAME"].startswith("test_"))
        out = Path(os.environ["BONIRA_OPERATIONS_EVIDENCE"]).resolve()
        self.assertTrue(out.is_dir())
        sink, acl = provision_sink()
        incident_id = str(uuid4())
        start = datetime.now(UTC)
        steps = []

        def step(name, **details):
            steps.append(
                {
                    "step": name,
                    "at": datetime.now(UTC).isoformat(),
                    "result": "PASS",
                    **details,
                }
            )

        # OP-01: actual loopback HTTP through the real Django middleware chain.
        with (
            override_settings(
                ROOT_URLCONF=__name__, ALLOWED_HOSTS=["127.0.0.1"], DEBUG=False
            ),
            activate(sink),
        ):
            server = make_server(
                "127.0.0.1", 0, WSGIHandler(), handler_class=QuietHandler
            )
            worker = Thread(target=server.serve_forever, daemon=True)
            worker.start()
            try:
                for failed, expected in ((True, 503), (False, 200)):
                    FAILURE.set() if failed else FAILURE.clear()
                    client = http.client.HTTPConnection(
                        "127.0.0.1", server.server_port, timeout=15
                    )
                    try:
                        client.request(
                            "GET",
                            "/qualification/?secret=exclude",
                            headers={"X-Request-ID": "untrusted-client-id"},
                        )
                        response = client.getresponse()
                        correlation = response.getheader("X-Request-ID")
                        self.assertEqual(response.status, expected)
                        self.assertNotEqual(correlation, "untrusted-client-id")
                        response.read()
                    finally:
                        client.close()
                    records = [
                        json.loads(p.read_text()) for p in sink.directory.glob("*.json")
                    ]
                    http_records = [
                        r
                        for r in records
                        if r.get("event") == "http.response"
                        and r["request_id"] == correlation
                    ]
                    self.assertEqual(len(http_records), 1)
                    self.assertEqual(http_records[0]["status_code"], expected)
                    alerts = [
                        r
                        for r in records
                        if r.get("signal") == "http.server_error"
                        and r["request_id"] == correlation
                    ]
                    self.assertEqual(len(alerts), int(failed))
                    self.assertNotIn("exclude", json.dumps(records))
                    step(
                        "HTTP_FAILURE_RECEIPT" if failed else "HTTP_RECOVERY",
                        correlation=correlation,
                        status=expected,
                    )
                # Actual local delivery outage: preserve the entire store under
                # a checked sibling name, then restore it in finally. No bytes
                # are deleted and no domain action is replayed.
                unavailable = sink.directory.with_name(sink.directory.name + "-offline")
                self.assertEqual(unavailable.parent, sink.directory.parent)
                self.assertFalse(unavailable.exists())
                diagnostic = io.StringIO()
                sink.directory.rename(unavailable)
                try:
                    with redirect_stderr(diagnostic):
                        client = http.client.HTTPConnection(
                            "127.0.0.1", server.server_port, timeout=15
                        )
                        try:
                            client.request("GET", "/qualification/")
                            response = client.getresponse()
                            self.assertEqual(response.status, 200)
                            response.read()
                        finally:
                            client.close()
                finally:
                    unavailable.rename(sink.directory)
                fallback = json.loads(diagnostic.getvalue())
                self.assertEqual(fallback["event"], "telemetry.delivery_failed")
                sink.write(
                    signal="telemetry.delivery_failed",
                    request_id=fallback["request_id"],
                )
                step(
                    "DELIVERY_OUTAGE_FALLBACK_AND_RECOVERY",
                    correlation=fallback["request_id"],
                    successful_response_preserved=True,
                    replayed_business_action=False,
                )
            finally:
                FAILURE.clear()
                server.shutdown()
                server.server_close()
                worker.join(timeout=10)
                self.assertFalse(worker.is_alive())

        # OP-02: a real child command uses only the isolated test DB. The fault
        # targets an unavailable loopback port, never the configured business DB.
        environment = os.environ.copy()
        database = connection.settings_dict
        for key, value in (
            ("DB_NAME", database["NAME"]),
            ("DB_USER", database["USER"]),
            ("DB_PASSWORD", database["PASSWORD"]),
            ("DB_HOST", database["HOST"]),
            ("DB_PORT", database["PORT"]),
        ):
            environment[key] = str(value)
        environment["DB_CONNECT_TIMEOUT"] = "1"
        command = [
            sys.executable,
            "manage.py",
            "operational_health",
            "--settings=config.settings.development",
        ]
        # Reserve an unlistened port throughout the failed probe.
        with socket.socket() as reserved:
            reserved.bind(("127.0.0.1", 0))
            failed_environment = {
                **environment,
                "DB_HOST": "127.0.0.1",
                "DB_PORT": str(reserved.getsockname()[1]),
            }
            for failed in (True, False):
                process = subprocess.run(
                    command,
                    env=failed_environment if failed else environment,
                    capture_output=True,
                    text=True,
                    timeout=40,
                    check=False,
                )
                self.assertEqual(process.returncode != 0, failed)
                record = json.loads(process.stdout)
                self.assertEqual(record["production_readiness"], "NOT_VALIDATED")
                self.assertEqual(
                    record["signals"][0],
                    "database.unreachable" if failed else "database.reachable",
                )
                self.assertEqual(record["signals"][1], "cache.reachable")
                for signal in record["signals"]:
                    sink.write(signal=signal)
                step(
                    "DEPENDENCY_FAILURE" if failed else "DEPENDENCY_RECOVERY",
                    exit_code=process.returncode,
                    signals=record["signals"],
                )

        # OP-03: existing service contracts with actual database audit evidence;
        # existing fixtures explicitly assign existing permissions and scope.
        support_fixture.SupportP9S16S20Tests.test_support_access_sod_scope_expiry_revocation_and_audit(
            self
        )
        revoked = SupportAccessRequest.objects.get(status="revoked")
        actions = sorted(
            set(
                AuditEvent.objects.filter(entity_id=str(revoked.pk)).values_list(
                    "action", flat=True
                )
            )
        )
        audit_trace = [
            {
                "id": str(event.pk),
                "action": event.action,
                "at": event.created_at.isoformat(),
                "source_request": str(revoked.pk),
                "actor": "requester"
                if event.actor_id == self.operator.pk
                else "tenant-confirmer"
                if event.actor_id == self.confirmer.pk
                else "independent-platform-approver"
                if event.actor_id == self.approver.pk
                else "other-authorized-fixture-actor",
            }
            for event in AuditEvent.objects.filter(entity_id=str(revoked.pk)).order_by(
                "created_at"
            )
        ]
        step("ACCESS_REQUEST_CONFIRM_APPROVE_USE_REVOKE_DENY", audit_actions=actions)
        expiring = request_access(
            organization=self.organization,
            actor=self.operator,
            purpose="expiry-drill",
            scope="case:read",
            expires_at=datetime.now(UTC) + timedelta(seconds=3),
        )
        confirm_access(
            organization=self.organization, actor=self.confirmer, request_id=expiring.pk
        )
        confirm_access(
            organization=self.organization,
            actor=self.approver,
            request_id=expiring.pk,
            platform=True,
        )
        time.sleep(
            max(0, (expiring.expires_at - datetime.now(UTC)).total_seconds()) + 0.1
        )
        with self.assertRaises(PermissionDenied):
            validate_access(
                organization=self.organization,
                actor=self.operator,
                request_id=expiring.pk,
                purpose="expiry-drill",
                scope="case:read",
            )
        step("EXPIRED_ACCESS_DENIED", clock="actual elapsed UTC, no timestamp mutation")

        # OP-04: executor restart preserves logs and receipts; no purge exists.
        before = {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sink.directory.glob("*.json")
        }
        reopened = DevelopmentOperationsSink(sink.directory)
        after = {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in reopened.directory.glob("*.json")
        }
        self.assertEqual(before, after)
        for p in sink.directory.glob("*.json"):
            record = json.loads(p.read_text())
            observed = record.get("observed_at", record.get("timestamp"))
            self.assertGreaterEqual(
                datetime.fromisoformat(record["retain_until"])
                - datetime.fromisoformat(observed),
                timedelta(days=30),
            )
        step("RESTART_AND_RETENTION", records_preserved=len(after), retention_days=30)
        acl_after = verify_private_tree(sink.directory)
        result = {
            "incident_id": incident_id,
            "started_at": start.isoformat(),
            "ended_at": datetime.now(UTC).isoformat(),
            "result": "PASS",
            "environment": "isolated-test-postgresql-loopback-development",
            "owner": "Human Decision Authority",
            "executor": "Codex",
            "authority": "EXT-0022-HUMAN-20261027",
            "runbooks": "OP-01..04",
            "escalation": "Human Decision Authority; no timer or SLA",
            "sink": str(sink.directory),
            "acl_before": acl,
            "acl_after": acl_after,
            "steps": steps,
            "synthetic_access_audit_trace": audit_trace,
            "receipt_hashes": after,
            "minimum_retain_until": (
                datetime.now(UTC) + timedelta(days=30)
            ).isoformat(),
            "production_readiness": "NOT_VALIDATED",
            "human_signoff": "NOT_EXECUTED",
        }
        # Restricted copy retains incident evidence with the logs; repository copy
        # contains sanitized synthetic references only, no identity/credential dump.
        data = json.dumps(result, indent=2)
        with (sink.directory / "incident.json").open("x", encoding="utf-8") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        (out / "SCENARIO.json").write_text(data, encoding="utf-8")
