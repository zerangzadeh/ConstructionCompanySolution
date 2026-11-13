# Recorded validation sources

Stage these files under `.scratch/project-detail-redesign` in a checkout matching the recorded source hashes. The relative paths in the scripts expect that runtime location. They are not production tools and must not run against an existing operational database.

The recorded run used new `project_redesign_original` and `project_redesign_retest` databases cloned from an empty, migrated B11 validation baseline on its loopback PostgreSQL cluster. `redesign_settings.py` reads the private runtime's `port.txt` and generated `secret.txt`; neither live secret nor session manifests are published. An independent environment can instead migrate a new empty private PostgreSQL database through all current migrations before seeding. Do not reset or overwrite an existing validation cluster to reproduce the run.

`seed.py` creates persisted synthetic Projects, WBS, Activities, contract/report and assignment/usage fixtures with explicit governed role assignments. It requires an empty original database. Capture `browser.py before` against the entry source, clone the seeded original database into a fresh retest database, implement the recorded delta, then use `protected_seed.py`, `browser.py after`, `verify_browser.py` and `equipment_final.py` with `REDESIGN_DB=project_redesign_retest`. The Platform fixture is synthetic. Do not rerun seed scripts on an already seeded database.

Tooling paths identify the installed Windows PostgreSQL 18, Google Chrome and existing Playwright Python runtime. Update local tooling paths when reproducing elsewhere. Screenshots and assertions use real Chrome and actual authorized application routes. The application itself gained no dependency.

The Django regression selection and its final results are in `acceptance-tests.log`; use a separate empty/migrated `test_project_redesign` database with `--reuse-db --ds=redesign_settings`. Preserve the catalog baseline and use the source tests' explicit authorities. `verify_actual.py` is a separate read-only development diagnostic tied to the reported development project and should be omitted when replaying synthetic validation elsewhere.

Keep original attempts separate from final evidence, verify the protected hashes and source delta, and stop only the owned private servers/cluster at closeout. Do not commit, push, publish, grant new operational permissions or perform production actions as part of replay.
