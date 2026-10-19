"""CEP-070 offline adapter controls; no application DB or production target."""

import json
import subprocess
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from scripts.backup_bundle import BackupError, BackupPlan, create_bundle


class BackupBundleTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        roots = {}
        for key in ("document_media", "configuration_metadata", "audit_operational"):
            roots[key] = self.root / key
            roots[key].mkdir()
            (roots[key] / "synthetic.txt").write_text(key, encoding="utf-8")
        self.tool = self.root / "pg_dump.exe"
        self.tool.write_bytes(b"mock executable")
        self.plan = BackupPlan(
            environment="non-production",
            source_revision="a" * 40,
            operator_reference="synthetic-operator",
            recovery_reference="synthetic-recovery",
            consistency_reference="synthetic-quiescent-fixture",
            database_service="synthetic_service",
            pg_dump=self.tool,
            roots=roots,
            destination=self.root / "bundle",
            command_timeout_seconds=60,
        )

    def _capture(self, args, **kwargs):
        file_arg = next(arg for arg in args if arg.startswith("--file="))
        Path(file_arg.removeprefix("--file=")).write_bytes(b"synthetic dump")
        return subprocess.CompletedProcess(args, 0)

    def test_complete_capture_preserves_all_classes_without_certification(self):
        with patch(
            "scripts.backup_bundle.subprocess.run", side_effect=self._capture
        ) as run:
            evidence = create_bundle(self.plan)
        self.assertEqual(evidence["capture_status"], "CAPTURED_NOT_RESTORE_VERIFIED")
        self.assertEqual(len(evidence["classes"]), 4)
        self.assertEqual(evidence["restore_status"], "NOT_EXECUTED")
        self.assertEqual(evidence["cross_store_consistency"], "UNVERIFIED")
        self.assertEqual(evidence["production_certification"], "NOT_EXECUTED")
        args, kwargs = run.call_args
        self.assertIn("--dbname=service=synthetic_service", args[0])
        self.assertEqual(kwargs["stderr"], subprocess.DEVNULL)
        self.assertEqual(kwargs["stdin"], subprocess.DEVNULL)
        self.assertNotIn(str(self.root), json.dumps(evidence))
        for key, source in self.plan.roots.items():
            self.assertEqual(
                (source / "synthetic.txt").read_bytes(),
                (self.plan.destination / key / "synthetic.txt").read_bytes(),
            )

    def test_invalid_plans_never_invoke_database_tool_or_create_output(self):
        invalid = [
            replace(self.plan, environment="production"),
            replace(self.plan, source_revision="main"),
            replace(self.plan, operator_reference=""),
            replace(self.plan, recovery_reference=""),
            replace(self.plan, consistency_reference=""),
            replace(self.plan, database_service="x password=secret"),
            replace(self.plan, command_timeout_seconds=0),
            replace(self.plan, roots={}),
            replace(self.plan, destination=self.root / "document_media" / "bundle"),
            replace(self.plan, destination=self.root),
            replace(self.plan, destination=Path("relative")),
            replace(self.plan, roots={key: self.root for key in self.plan.roots}),
        ]
        with patch("scripts.backup_bundle.subprocess.run") as run:
            for plan in invalid:
                with self.subTest(plan=plan), self.assertRaises(BackupError):
                    create_bundle(plan)
            run.assert_not_called()
        self.assertFalse(self.plan.destination.exists())

    def test_failed_dump_retains_failure_without_sensitive_tool_output(self):
        with (
            patch(
                "scripts.backup_bundle.subprocess.run",
                return_value=subprocess.CompletedProcess([], 1),
            ),
            self.assertRaises(BackupError),
        ):
            create_bundle(self.plan)
        evidence = json.loads((self.plan.destination / "capture.json").read_text())
        self.assertEqual(evidence["capture_status"], "FAILED")
        self.assertEqual(evidence["database_tool_exit_code"], 1)
        self.assertEqual(evidence["classes"], {})

    def test_timeout_retains_failure_and_redacts_exception_message(self):
        with (
            patch(
                "scripts.backup_bundle.subprocess.run",
                side_effect=subprocess.TimeoutExpired("password=secret", 1),
            ),
            self.assertRaises(BackupError),
        ):
            create_bundle(self.plan)
        text = (self.plan.destination / "capture.json").read_text()
        self.assertNotIn("secret", text)
        self.assertEqual(json.loads(text)["failure_type"], "TimeoutExpired")

    def test_source_change_during_dump_cannot_be_reported_captured(self):
        def changing_dump(args, **kwargs):
            result = self._capture(args, **kwargs)
            (self.plan.roots["document_media"] / "new.txt").write_bytes(b"changed")
            return result

        with (
            patch("scripts.backup_bundle.subprocess.run", side_effect=changing_dump),
            self.assertRaises(BackupError),
        ):
            create_bundle(self.plan)
        evidence = json.loads((self.plan.destination / "capture.json").read_text())
        self.assertEqual(evidence["capture_status"], "FAILED")

    def test_existing_bundle_is_never_overwritten(self):
        self.plan.destination.mkdir()
        marker = self.plan.destination / "capture.json"
        marker.write_bytes(b"retained history")
        with self.assertRaises(BackupError):
            create_bundle(self.plan)
        self.assertEqual(marker.read_bytes(), b"retained history")

    def test_links_are_rejected_before_reading_target(self):
        from scripts.backup_bundle import _reject_link

        # Portable coverage of the Windows junction/reparse-point branch.
        fake_stat = type("Metadata", (), {"st_file_attributes": 1024})()
        with (
            patch.object(Path, "lstat", return_value=fake_stat),
            patch.object(Path, "is_symlink", return_value=False),
            self.assertRaises(BackupError),
        ):
            _reject_link(self.root)

    def test_zero_exit_without_dump_bytes_still_fails(self):
        with (
            patch(
                "scripts.backup_bundle.subprocess.run",
                return_value=subprocess.CompletedProcess([], 0),
            ),
            self.assertRaises(BackupError),
        ):
            create_bundle(self.plan)
        self.assertEqual(
            json.loads((self.plan.destination / "capture.json").read_text())[
                "capture_status"
            ],
            "FAILED",
        )

    def test_nested_reparse_point_fails_before_database_capture(self):
        from scripts.backup_bundle import _reject_link

        def reject_nested(path):
            if path.name == "synthetic.txt":
                raise BackupError("Synthetic nested reparse point")
            _reject_link(path)

        with (
            patch("scripts.backup_bundle._reject_link", side_effect=reject_nested),
            patch("scripts.backup_bundle.subprocess.run") as run,
        ):
            with self.assertRaises(BackupError):
                create_bundle(self.plan)
            run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
