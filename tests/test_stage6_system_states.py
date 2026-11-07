"""Shared feedback browser contract using rendered Django components, no DB writes."""

import json
import os
import subprocess
from pathlib import Path

from django import forms
from django.contrib.auth.models import AnonymousUser
from django.contrib.messages import constants
from django.contrib.messages.storage.base import Message
from django.contrib.messages.storage.cookie import CookieStorage
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase
from django.urls import resolve
from django.utils.safestring import mark_safe
from django.views.defaults import page_not_found, permission_denied, server_error

ROOT = Path(__file__).resolve().parents[1]


class Stage6SystemStatesTests(SimpleTestCase):
    def test_workflow_partial_consumes_messages_without_next_request_replay(self):
        request = RequestFactory().get("/", HTTP_HX_REQUEST="true")
        request.user = AnonymousUser()
        storage = CookieStorage(request)
        storage.add(constants.SUCCESS, "کار با موفقیت اخذ شد.")
        partial = render_to_string(
            "workflows/_work_item_row.html",
            {"item": {}, "messages": storage},
            request=request,
        )
        self.assertIn('hx-swap-oob="beforeend:#bonira-feedback"', partial)
        self.assertEqual(partial.count("کار با موفقیت اخذ شد."), 1)
        self.assertTrue(storage.used)
        response = HttpResponse(partial)
        storage.update(response)
        next_request = RequestFactory().get(
            "/", HTTP_COOKIE=response.cookies.output(header="", sep=";")
        )
        self.assertEqual(list(CookieStorage(next_request)), [])

    def test_real_browser_feedback_contract(self):
        request = RequestFactory().get("/")
        request.user = AnonymousUser()
        request.organization = None
        request.resolver_match = resolve("/")
        output = ROOT / "output/stage6-system-states"
        output.mkdir(parents=True, exist_ok=True)
        shell = render_to_string(
            "base.html", {"request": request, "product_navigation_groups": []}
        )
        (output / "shell.html").write_text(shell, encoding="utf-8")
        self.addCleanup((output / "shell.html").unlink, missing_ok=True)
        messages = {
            level: render_to_string(
                "components/messages.html",
                {"messages": [Message(getattr(constants, level.upper()), text)]},
            )
            for level, text in {
                "success": "اطلاعات با موفقیت ثبت شد.",
                "error": "ثبت اطلاعات ممکن نشد.",
                "warning": "پیش از ادامه اطلاعات را بررسی کنید.",
                "info": "اطلاعات به‌روزرسانی شد.",
            }.items()
        }

        class SampleForm(forms.Form):
            title = forms.CharField(label="عنوان", required=True)

        form = SampleForm({"title": ""})
        validation = render_to_string("components/form_errors.html", {"form": form})
        validation += render_to_string(
            "components/form_field.html", {"field": form["title"]}
        )
        states = {}
        for status, view, args in (
            (403, permission_denied, (Exception("private"),)),
            (404, page_not_found, (Exception("private"),)),
            (500, server_error, ()),
        ):
            response = view(request, *args)
            self.assertEqual(response.status_code, status)
            self.assertNotIn("private", response.content.decode())
            states[str(status)] = response.content.decode()
        states["empty"] = render_to_string(
            "components/empty_state.html",
            {
                "empty_title": "موردی یافت نشد",
                "empty_description": "در حال حاضر اطلاعاتی برای نمایش وجود ندارد.",
            },
        )
        states["badge"] = render_to_string(
            "components/status_badge.html", {"status": "approved"}
        )
        (output / "fixtures.json").write_text(
            json.dumps(
                {"messages": messages, "validation": validation, "states": states},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        unsafe = render_to_string(
            "components/messages.html",
            {
                "messages": [
                    Message(constants.ERROR, mark_safe("<img src=x onerror=alert(1)>"))
                ]
            },
        )
        self.assertIn("&lt;img", unsafe)
        self.assertNotIn("<img", unsafe)
        result = subprocess.run(
            [
                "node",
                str(ROOT / "scripts/verification/stage6_browser.mjs"),
                str(output),
            ],
            cwd=ROOT,
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=240,
            check=False,
        )
        (output / "command.txt").write_text(
            f"exit={result.returncode}\n{result.stdout}\n{result.stderr}",
            encoding="utf-8",
        )
        self.assertEqual(result.returncode, 0, (result.stderr or result.stdout)[-6000:])
