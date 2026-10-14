# CEP-010 Execution Manifest

- Authorization: AUTH-BATCH-001; bounded schema migration resolution (2026-10-14).
- Primary IMB: IMB-0069. GATE-01 and Human Sign-off remain open.
- Branch: `cep/CEP-010-person-workrelationship`
- HEAD: `0b0cfcdabb93e4e6215d6f2805e763dd82f99cf4` (local `main`).
- Grounding: clean worktree; `git status --short`, `git diff --name-status`, and `git diff --stat` were empty before this manifest. No Person or WorkRelationship model exists. Workforce migration head is 0008. Existing Employee and assignments are authoritative legacy records.
- CEP-010-FINDING-001 / BLOCKER-MIGRATION: resolved by the Human Product Owner''s bounded schema migration authorization. Bulk migration and cutover remain excluded.

## Actual execution touch set, recorded before product mutation

- `apps/workforce/models.py`: Person (UUID, organization, name, optional User); WorkRelationship (UUID, organization, Person, employee number, effective start/end, optional legacy Employee); WorkRelationshipRevision (episode version/effective dates and actor). Add tenant, date, identity, and immutability validation plus relevant unique/check constraints and indexes. Existing Employee fields remain intact.
- `apps/workforce/person_services.py`: create/end episode and legacy Employee resolution; no UI, cutover, or bulk backfill.
- `apps/workforce/migrations/0009_cep010_person_workrelationship.py`: schema-only CreateModel/AddConstraint/AddIndex operations; no RunPython.
- `apps/workforce/test_cep010_person_workrelationship.py`: model, service, tenant/object, compatibility, history, and regression tests.
- `CEP-010_{EXECUTION_MANIFEST.md,ACCEPTANCE_MAPPING.csv,EVIDENCE_MANIFEST.csv,CHANGE_MANIFEST.csv,COMPLETION_REPORT.md}`: execution records.
- `ROADMAP.md`, `docs/architecture/DOMAIN_AND_DATA_MODEL.md`: bounded disposition and current/target ownership reconciliation only.

Migration verification will use the configured non-production database. Existing Employee/assignment rows must remain unchanged; no Person/relationship rows are synthesized. Any required touch outside this set or any bulk data operation requires a new finding and stop.

