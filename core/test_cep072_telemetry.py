"""Technical telemetry boundaries; no operating certification or business DB."""

import io
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import patch
from uuid import UUID

from django.http import HttpResponse
from django.test import Client, RequestFactory, SimpleTestCase
from django.urls import reverse

from core.telemetry import (
    RequestJsonFormatter,
    RequestTelemetryMiddleware,
    current_request_id,
)


class RequestTelemetryTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.stream = io.StringIO()
        self.handler = logging.StreamHandler(self.stream)
        self.handler.setFormatter(RequestJsonFormatter())
        self.logger = logging.getLogger("bonira.request")
        self.old_handlers = self.logger.handlers[:]
        self.logger.handlers = [self.handler]
        self.addCleanup(setattr, self.logger, "handlers", self.old_handlers)

    def records(self):
        return [json.loads(line) for line in self.stream.getvalue().splitlines()]

    def test_correlates_without_recording_sensitive_inputs(self):
        request = self.factory.post(
            "/private/person/secret-identifier/?token=secret-query",
            {"password": "secret-body"},
            HTTP_AUTHORIZATION="Bearer secret-header",
            HTTP_X_REQUEST_ID="secret-client-id\nforged-log",
        )
        request.resolver_match = SimpleNamespace(view_name="workforce:detail")
        seen = []

        def view(req):
            seen.append(current_request_id())
            return HttpResponse("unchanged", status=201)

        response = RequestTelemetryMiddleware(view)(request)
        record = self.records()[0]
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.content, b"unchanged")
        self.assertEqual(str(UUID(response["X-Request-ID"])), seen[0])
        self.assertEqual(record["request_id"], seen[0])
        self.assertEqual(record["route"], "workforce:detail")
        self.assertEqual(record["status_code"], 201)
        self.assertGreaterEqual(record["duration_ms"], 0)
        self.assertNotIn("secret", self.stream.getvalue())
        self.assertIsNone(current_request_id())

    def test_denied_and_failed_responses_keep_status_and_unique_correlation(self):
        identifiers = []
        for status in (302, 403, 404, 500, 503):
            with self.subTest(status=status):
                response = RequestTelemetryMiddleware(
                    lambda request, code=status: HttpResponse(status=code)
                )(self.factory.get("/"))
                self.assertEqual(response.status_code, status)
                identifiers.append(response["X-Request-ID"])
                self.assertIsNone(current_request_id())
        self.assertEqual(len(set(identifiers)), 5)
        self.assertEqual(
            [r["status_code"] for r in self.records()], [302, 403, 404, 500, 503]
        )

    def test_exception_propagates_without_payload_and_cleans_context(self):
        def broken(request):
            raise ValueError("secret-exception")

        with self.assertRaisesMessage(ValueError, "secret-exception"):
            RequestTelemetryMiddleware(broken)(self.factory.get("/"))
        self.assertEqual(self.records()[0]["status_code"], 500)
        self.assertNotIn("secret", self.stream.getvalue())
        self.assertIsNone(current_request_id())

    def test_delivery_failure_does_not_replace_committed_response(self):
        stream = io.StringIO()
        with (
            patch("core.telemetry._logger.log", side_effect=OSError("secret-sink")),
            patch("core.telemetry.sys.stderr", stream),
        ):
            response = RequestTelemetryMiddleware(
                lambda request: HttpResponse("committed", status=201)
            )(self.factory.post("/"))
        self.assertEqual(response.content, b"committed")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            json.loads(stream.getvalue())["event"], "telemetry.delivery_failed"
        )
        self.assertNotIn("secret", stream.getvalue())
        self.assertIsNone(current_request_id())

    def test_formatter_ignores_message_exception_and_unapproved_fields(self):
        record = logging.LogRecord(
            "bonira.request", 40, "secret-path", 1, "secret", (), None
        )
        record.exc_text = "secret-traceback"
        record.payload = {"token": "secret"}
        record.route = "/secret-path?token=secret"
        record.request_id = "secret-header"
        data = json.loads(RequestJsonFormatter().format(record))
        self.assertIsNone(data["route"])
        self.assertIsNone(data["request_id"])
        self.assertNotIn("secret", json.dumps(data))

    def test_nested_and_concurrent_requests_keep_separate_context(self):
        def nested(request):
            outer_id = current_request_id()
            RequestTelemetryMiddleware(lambda inner: HttpResponse())(
                self.factory.get("/")
            )
            self.assertEqual(current_request_id(), outer_id)
            return HttpResponse()

        middleware = RequestTelemetryMiddleware(nested)
        with ThreadPoolExecutor(max_workers=2) as executor:
            responses = list(
                executor.map(lambda _: middleware(self.factory.get("/")), range(4))
            )
        self.assertEqual(len({r["X-Request-ID"] for r in responses}), 4)
        self.assertEqual(len({r["request_id"] for r in self.records()}), 8)
        self.assertIsNone(current_request_id())

    def test_real_middleware_preserves_authentication_and_csrf_denial(self):
        client = Client(enforce_csrf_checks=True)
        anonymous = client.get(reverse("home"))
        self.assertEqual(anonymous.status_code, 302)
        self.assertIn(reverse("accounts:login"), anonymous["Location"])
        rejected = client.post(
            reverse("accounts:login"),
            {"username": "secret-username", "password": "secret-password"},
        )
        self.assertEqual(rejected.status_code, 403)
        self.assertNotEqual(anonymous["X-Request-ID"], rejected["X-Request-ID"])
        self.assertEqual([r["status_code"] for r in self.records()], [302, 403])
        self.assertNotIn("secret", self.stream.getvalue())
