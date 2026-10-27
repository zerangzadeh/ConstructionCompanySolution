"""Focused control tests. Future-date tests are simulations, never elapsed proof."""

import json
import os
import subprocess
import tempfile
import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from itertools import pairwise
from pathlib import Path
from unittest.mock import patch

from scripts.backup_bundle import BackupPlan, file_hash
from scripts.cep070_recovery_controls import (
    ControlError,
    RecoveryControls,
    create_private_store,
    exclusive_store,
    load_policy,
    verify_private_tree,
)


class RecoveryControlTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="cep070_control_test_")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.acl = patch(
            "scripts.cep070_recovery_controls.verify_private_tree",
            return_value={"status": "PASS"},
        )
        self.acl.start()
        self.addCleanup(self.acl.stop)
        self.store = self.root / "store"
        self.store.mkdir()
        self.controls = RecoveryControls(self.store)
        roots = {}
        for key in ("document_media", "configuration_metadata", "audit_operational"):
            roots[key] = self.root / key
            roots[key].mkdir()
            (roots[key] / "synthetic.txt").write_text(key, encoding="utf-8")
        self.plan = BackupPlan(
            environment="non-production",
            source_revision="a" * 40,
            operator_reference="Codex-session-technical-executor",
            recovery_reference="EXT-0020-HUMAN-20261027",
            consistency_reference="isolated-quiescent-no-other-writers",
            database_service="synthetic_service",
            pg_dump=Path(__file__).resolve(),
            roots=roots,
            destination=self.root / "unused",
            command_timeout_seconds=180,
        )

    def dump(self, args, **kwargs):
        argument = next(arg for arg in args if arg.startswith("--file="))
        Path(argument.removeprefix("--file=")).write_bytes(b"synthetic custom dump")
        return subprocess.CompletedProcess(args, 0)

    def capture(self):
        with patch("scripts.backup_bundle.subprocess.run", side_effect=self.dump):
            return self.controls.capture(self.plan)

    def events(self):
        return [
            json.loads(p.read_text()) for p in (self.store / "events").glob("*.json")
        ]

    def test_production_or_changed_objectives_fail_closed(self):
        policy = load_policy()
        for field, value in {
            "environment": "production",
            "production_authorized": True,
            "production_equivalent": True,
            "pitr_required": True,
            "rpo_seconds": 901,
            "rto_seconds": 3601,
            "backup_interval_seconds": 901,
            "minimum_retention_days": 29,
            "restore_test_interval_days": 31,
            "purge_authorized": True,
            "rpo_seconds_float": 900.0,
        }.items():
            with self.subTest(field=field):
                actual = "rpo_seconds" if field == "rpo_seconds_float" else field
                changed = {**policy, actual: value}
                path = self.root / "altered-policy.json"
                path.write_text(json.dumps(changed))
                with self.assertRaises(ControlError):
                    load_policy(path)

    def test_capture_keeps_previous_bundles_and_covers_all_classes(self):
        first = self.capture()
        digest = file_hash(first / "database.dump")
        second = self.capture()
        self.assertNotEqual(first, second)
        self.assertEqual(file_hash(first / "database.dump"), digest)
        self.assertEqual(
            set(self.controls.validate_bundle(second)["classes"]),
            set(load_policy()["data_classes"]),
        )

    def test_failed_capture_preserves_last_good_and_sanitizes_error(self):
        good = self.capture()
        previous = dict(self.controls.state)
        with (
            patch(
                "scripts.backup_bundle.subprocess.run",
                side_effect=subprocess.TimeoutExpired("private-secret-marker", 180),
            ),
            self.assertRaises(ControlError),
        ):
            self.controls.capture(self.plan)
        self.assertEqual(self.controls.state, previous)
        self.assertTrue(good.is_dir())
        self.assertEqual(sum(e["event"] == "CAPTURE_FAILED" for e in self.events()), 1)
        self.assertNotIn("private-secret-marker", json.dumps(self.events()))
        status = self.controls.retention_status(datetime.now(UTC))
        self.assertTrue(
            any(s["state"] == "QUARANTINED_FAILED_CAPTURE_NO_PURGE" for s in status)
        )

    def test_corrupted_dump_or_media_is_never_a_valid_recovery_point(self):
        for relative in ("database.dump", "document_media/synthetic.txt"):
            with self.subTest(relative=relative):
                bundle = self.capture()
                (bundle / relative).write_bytes(b"corrupted")
                with self.assertRaises(ControlError):
                    self.controls.validate_bundle(bundle)

    def test_retention_boundary_simulation_never_deletes_bytes(self):
        bundle = self.capture()
        receipt = json.loads((bundle / "retention.json").read_text())
        until = datetime.fromisoformat(receipt["retain_until"])
        before = {
            p.relative_to(bundle).as_posix(): file_hash(p)
            for p in bundle.rglob("*")
            if p.is_file()
        }
        self.assertEqual(
            self.controls.retention_status(until - timedelta(microseconds=1))[0][
                "state"
            ],
            "PROTECTED_RETENTION",
        )
        self.assertEqual(
            self.controls.retention_status(until)[0]["state"],
            "DISPOSITION_REQUIRES_SEPARATE_AUTHORITY",
        )
        after = {
            p.relative_to(bundle).as_posix(): file_hash(p)
            for p in bundle.rglob("*")
            if p.is_file()
        }
        self.assertEqual(before, after)

    def test_shortened_retention_or_changed_receipt_is_rejected(self):
        bundle = self.capture()
        path = bundle / "retention.json"
        original = json.loads(path.read_text())
        for changes in (
            {"retain_until": original["completed_at"]},
            {"purge_authorized": True},
            {"capture_manifest_sha256": "0" * 64},
        ):
            with self.subTest(changes=changes):
                path.write_text(json.dumps({**original, **changes}))
                with self.assertRaises(ControlError):
                    self.controls.retention_status(datetime.now(UTC))

    def test_due_dates_survive_restart_and_thirty_day_boundary_simulation(self):
        bundle = self.capture()
        started = datetime(2026, 10, 27, tzinfo=UTC)
        with patch(
            "scripts.cep070_recovery_controls.utc_now",
            return_value=started + timedelta(seconds=20),
        ):
            result = self.controls.record_restore(
                bundle=bundle, started=started, rpo_seconds=0, passed=True
            )
        restarted = RecoveryControls(self.store)
        next_test = datetime.fromisoformat(restarted.state["next_restore_test_at"])
        self.assertEqual(next_test, started + timedelta(seconds=20, days=30))
        self.assertFalse(restarted.restore_due(next_test - timedelta(microseconds=1)))
        self.assertTrue(restarted.restore_due(next_test))
        self.assertEqual(result["rto_seconds"], 20)
        next_backup = datetime.fromisoformat(restarted.state["next_backup_at"])
        self.assertFalse(restarted.backup_due(next_backup - timedelta(microseconds=1)))
        self.assertTrue(restarted.backup_due(next_backup))

    def test_failed_recovery_or_exceeded_objectives_cannot_advance_drill(self):
        bundle = self.capture()
        started = datetime(2026, 10, 27, tzinfo=UTC)
        for rpo, rto, passed in (
            (901, 20, True),
            (0, 3601, True),
            (-1, 20, True),
            (0, 20, False),
        ):
            with self.subTest(rpo=rpo, rto=rto, passed=passed):
                with (
                    patch(
                        "scripts.cep070_recovery_controls.utc_now",
                        return_value=started + timedelta(seconds=rto),
                    ),
                    self.assertRaises(ControlError),
                ):
                    self.controls.record_restore(
                        bundle=bundle,
                        started=started,
                        rpo_seconds=rpo,
                        passed=passed,
                    )
                self.assertNotIn("next_restore_test_at", self.controls.state)
        self.assertEqual(sum(e["event"] == "RESTORE_FAILED" for e in self.events()), 4)

    def test_unapproved_capture_scope_and_other_store_fail_before_dump(self):
        with patch("scripts.backup_bundle.subprocess.run") as run:
            for plan in (
                replace(self.plan, environment="production"),
                replace(self.plan, recovery_reference="UNAPPROVED"),
            ):
                with self.assertRaises(ControlError):
                    self.controls.capture(plan)
            run.assert_not_called()
        with self.assertRaises(ControlError):
            self.controls.validate_bundle(self.root)

    def test_changed_policy_on_restart_fails_closed(self):
        self.capture()
        data = json.loads(self.controls.state_path.read_text())
        data["policy_sha256"] = "0" * 64
        self.controls.state_path.write_text(json.dumps(data))
        with self.assertRaises(ControlError):
            RecoveryControls(self.store)

    def test_os_lock_prevents_overlapping_workers(self):
        with (
            exclusive_store(self.store),
            self.assertRaises(ControlError),
            exclusive_store(self.store),
        ):
            self.fail("Overlapping worker acquired the OS lock")
        with exclusive_store(self.store):
            pass

    def test_bounded_worker_cadence_and_restore_callback_clock_simulation(self):
        clock = [datetime(2026, 10, 27, tzinfo=UTC)]
        captures = []
        restores = []

        def capture(plan):
            captures.append(clock[0])
            self.controls.state["next_backup_at"] = (
                clock[0] + timedelta(seconds=900)
            ).isoformat()
            return self.root / "simulated-bundle"

        def restore(bundle):
            restores.append(clock[0])
            return {"rpo_seconds": 0, "passed": True}

        def recorded(**values):
            self.controls.state["next_restore_test_at"] = (
                clock[0] + timedelta(days=30)
            ).isoformat()

        with (
            patch(
                "scripts.cep070_recovery_controls.utc_now", side_effect=lambda: clock[0]
            ),
            patch(
                "scripts.cep070_recovery_controls.time.sleep",
                side_effect=lambda _: clock.__setitem__(
                    0, clock[0] + timedelta(seconds=30)
                ),
            ),
            patch.object(self.controls, "capture", side_effect=capture),
            patch.object(self.controls, "record_restore", side_effect=recorded),
        ):
            self.controls.run_cycles(self.plan, cycles=3, restore=restore)
        self.assertEqual(
            [(b - a).total_seconds() for a, b in pairwise(captures)],
            [720, 720],
        )
        self.assertEqual(len(restores), 1)
        self.assertTrue(
            any(
                e["event"] == "BOUNDED_WORKER_STOPPED"
                and e["unattended_service_installed"] is False
                for e in self.events()
            )
        )

    def test_failed_restore_callback_is_audited_without_advancing_due_date(self):
        with (
            patch("scripts.backup_bundle.subprocess.run", side_effect=self.dump),
            self.assertRaises(ControlError),
        ):
            self.controls.run_cycles(
                self.plan,
                cycles=1,
                restore=lambda _: (_ for _ in ()).throw(
                    RuntimeError("private-secret-marker")
                ),
            )
        self.assertNotIn("next_restore_test_at", self.controls.state)
        self.assertTrue(any(e["event"] == "RESTORE_FAILED" for e in self.events()))
        self.assertNotIn("private-secret-marker", json.dumps(self.events()))


@unittest.skipUnless(os.name == "nt", "Approved target is Windows")
class WindowsFilesystemControlTests(unittest.TestCase):
    def test_actual_restricted_store_inherits_to_children_and_rejects_plain_boundary(
        self,
    ):
        with tempfile.TemporaryDirectory(prefix="cep070_acl_control_") as folder:
            parent = Path(folder).resolve()
            with self.assertRaises(ControlError):
                verify_private_tree(parent)
            store = create_private_store(parent)
            nested = store / "synthetic"
            nested.mkdir()
            (nested / "only-synthetic.txt").write_text("no secrets")
            result = verify_private_tree(store)
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(result["paths_checked"], 3)
            self.assertEqual(
                verify_private_tree(nested, boundary=False)["status"], "PASS"
            )


if __name__ == "__main__":
    unittest.main()
