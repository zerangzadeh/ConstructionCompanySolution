# RV-007 Final Closure — 2026-10-23

**EXECUTION PARTIAL. RV-007: BLOCKED_CANONICAL_TEMPORAL_PREREQUISITE.**
Current Wave C result: **WAVE_C_BLOCKED** (11 prior scenario results retained;
RV-007 unresolved and additional regression attribution UTV).
`WAVE_C_COMPLETE_WITH_EXPLICIT_BASELINE_DEBT` is not issued.

## Authority and bounded execution

Human request: current Development only; one synthetic past-close RFQ through
canonical services, 24 hours from close to allowed opening, no direct database
fabrication/authorization bypass, retained RFQ unchanged, no Production/Git,
no Wave D or CEP-078/079. Repository main/HEAD `43ac319c6e73e48ca9626461b73987922c498ec3` and origin/main
match. Existing dirty source is preserved. Touch set is this evidence directory
and append-only result/report reconciliation. No product source, schema, migration,
dependency, permission, scope, policy, production or CEP lifecycle change.

## Canonical blocker and reproduction

`capture_quote_revision` assigns server `received_at=timezone.now()` and marks
receipt after close `is_late=True` (quote_services.py:165–180).
`submit_quote_revision` rejects server time after version close (line 254).
Backdating the supplied `supplier_submitted_at` does not replace receipt time.
The manifest requires SUBMITTED, not late, and both receipt/submission at or
before close (rfq_services.py:177–193). Custody requires that effective submitted
manifest entry (custody_services.py:289–315); opening also requires it
(opening_services.py:178–211). The portal rejects after close too
(portal_services.py:389–391,523–524). No canonical retrospective quote-import
path was found in Procurement services or management commands. The existing
workflow backfill imports Purchase Request workflow history, not RFQ quotes.

The [real Development probe](FEASIBILITY.json) uses existing authorized tenant,
project, approved Purchase Request, supplier and independent specialists. It
creates and issues exactly one synthetic RFQ **inside a transaction that is
rolled back**: close 25 hours ago, earliest opening 24 hours after close (one hour
ago). It captures a SHA-256 of benign synthetic bytes without representing them
as custodial/scan evidence. Canonical submission fails with the explicit
after-deadline error; close records `no_effective_submission`; opening is denied.
The entire probe rolls back, including its audits. **No new RFQ is retained.**
The initial probe also rolled back after a source-reference format validation
error; the final probe uses a valid technical source reference.

A compliant retained fixture cannot be completed now with these services.
Completing it requires a separately governed canonical historical-import path,
or an on-time submitted fixture followed by the real close and 24-hour wait.
Neither a clock patch nor direct date/state writes were used. No permission was
granted, no authorization check was bypassed, and no CLEAN verdict was fabricated.

## Retained evidence and runtime limits

The retained `WAVE-C-RFQ-A` remains issued, close **October 24, 2026 14:46:11 Tehran**,
earliest opening **October 25, 2026 14:46:11 Tehran**; the gap is exactly 24 hours.
Its real early close and opening attempts were denied in rollback transactions.
The opening denial first reaches the missing closed/effective manifest guard;
it is **not isolated live proof of the later 24-hour guard**. The opening unit
suite separately exercises the earliest-opening boundary in its test database.
All Procurement model fingerprints match before/after; retained row hash matches.

The [ten-requirement matrix](RV007_MATRIX.json) distinguishes isolated tests from
live evidence. Positive opening/independent approval/confidential comparison,
valid source/custody/scan and opened-stage desktop/mobile verification remain
unexecuted. New-fixture live same-tenant/site/cross-tenant/manipulated-action
controls are not claimed PASS. A diagnostic Chrome tab reached the login page
and was closed without altering authentication. No authenticated desktop/mobile
success is claimed and no UI success was inferred from HTTP or unit tests.

## Validation and integrity

Focused: **9 passed in 71.12s (0:01:11)**.
Affected: **27 failed, 25 passed, 4 subtests passed in 158.81s (0:02:38)**.
See [focused output](focused.txt), [affected output](affected.txt), JUnit XML and
[validation](VALIDATION.json) for actual coverage/failure details. These are
isolated test-database runs, not the requested populated live Development journey.
Django checks PASS. No schema change; Development migration plan is empty.
All entry product-source fingerprints and Git HEAD/index hashes are unchanged.
The prior accepted [baseline attribution](../wave_c_final_closure/REGRESSION_ATTRIBUTION.json)
remains explicit; full-repository regression is not claimed green. The additional
27 failures occur before intended assertions: one duplicate active role assignment,
18 shared opening-approver setup denials and eight shared buyer setup close denials.
Product source matches this session's entry, but that does not prove these
broader failures are unrelated to earlier Wave C source changes. Their historical
attribution is **UTV**, not accepted baseline debt and not a passing regression.
No unrelated test repair or permission weakening was performed. The earlier
zero-unresolved-regression claim covered a smaller selection and is not extended
to this broader result.

CEP Registry/roadmap/previous closed findings remain unchanged. Human Sign-off,
Production Certification/Cutover, Wave D, CEP-078/079, branch/worktree creation,
Git add/commit/push/merge: **NOT EXECUTED**. Production: **UNTOUCHED**.

**STOP.**
