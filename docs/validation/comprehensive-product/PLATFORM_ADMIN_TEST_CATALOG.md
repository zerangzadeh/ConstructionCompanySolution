# BONIRA Platform Admin test catalog

The internal workspace is allowlisted under MVP for effective Platform Admins. It uses independent platform permissions and explicit tenant grants for delegated member-role actions. The tenant user workspace and technical Django Admin are separate surfaces. Use accounts with split grants for PA-11 and keep the local technical recovery account out of ordinary steps.

Sources: organization URL registry; organization platform_console, platform_views and platform_companies; account platform_user_views and platform_user_services; organization authorization and permission_registry; platform assessment and implementation reports listed in Coverage and Gaps.

Supported controls include account deactivation/reactivation, registered-email recovery, temporary password with forced change, company suspend/reactivate, retry onboarding, governed platform roles and tenant delegation, policy catalogs, filtered platform audit and dependency reachability. Platform Settings reports the active profile read-only. Account deletion, tenant-wide cancellation/export/offboarding, arbitrary policy toggles, impersonation, adoption analytics and independent uptime certification have no comparable supported workspace flow in the inspected implementation. MFA/step-up and production SMTP delivery remain external/unverified here.

[Exact route/action worklist](TEST_EXECUTION_MATRIX.csv)

## Scenarios

<a id="pa-01"></a>

### PA-01 · Open the Platform workspace and validate dashboard

**Batch and status** · B10 · NOT_RUN · 1 worklist rows

**Actors and seed** · effective PA, tenant owner, inactive/revoked PA, recovery superuser. Two companies, registered users, platform activity and one incomplete onboarding fixture

**Browser sequence** · Sign in without next, use dashboard, sidebar and mobile menu. Compare safe next handling and each of eight destinations. Check dashboard counts, recent events and health cards.

**Expected UI** · Authorized default landing and controls, correct counts and localized empty state. Active company context does not redefine platform target.

**Persisted state, cross-module and negative checks** · Reconcile Organization, User and membership count definitions and filtered event windows against source. Deny tenant-only and revoked PA. Verify superuser follows actual bootstrap/recovery gate.

**Evidence** · 1440/1024/390 shell, dashboard witnesses and denied requests.

**Acceptance** · PASS requires the sequence, UI, authoritative state and denial assertions to match with evidence. Test with an insufficiently granted and foreign actor wherever the target is tenant or object scoped. Preserve the baseline and isolate fixture failures.

**Baseline references** · apps/organizations/urls.py and the per-row view, permissions and source references in the master inventory. apps/organizations/test_platform_console.py.

<a id="pa-02"></a>

### PA-02 · Create company and complete or retry onboarding

**Batch and status** · B10 · NOT_RUN · 3 worklist rows

**Actors and seed** · PA with company creation permission, eligible separate owner, viewer. Unique company slug and separate active initial owner, incomplete company with single effective owner and ambiguous case

**Browser sequence** · Use Create Company, supply governed owner, submit and follow details. Use retry on incomplete sample and re-open role/workflow status.

**Expected UI** · Company, creator and current owners/local administrators clear, failed retry gives useful guidance.

**Persisted state, cross-module and negative checks** · Verify atomic Organization + initial owner membership + audit + starter workflows. Force test-only failure per existing tests to prove rollback. Probe duplicate, self/inactive owner and ambiguous retry.

**Evidence** · Company/owner/step snapshots and before/after failure audit.

**Acceptance** · PASS requires the sequence, UI, authoritative state and denial assertions to match with evidence. Test with an insufficiently granted and foreign actor wherever the target is tenant or object scoped. Preserve the baseline and isolate fixture failures.

**Baseline references** · apps/organizations/urls.py and the per-row view, permissions and source references in the master inventory. apps/organizations/test_platform_console.py.

<a id="pa-03"></a>

### PA-03 · Search, edit, suspend and reactivate a company

**Batch and status** · B10 · NOT_RUN · 5 worklist rows

**Actors and seed** · PA with view/manage/suspend, local admin and affected member. Active companies A/B, suspended sample, independent sessions

**Browser sequence** · Use company search/filter, open detail/edit, try protected field change and cancel confirmation once. Suspend with reason, test tenant UI, reactivate and retest.

**Expected UI** · Target company named independently of active tenant. Status and recorded reason visible, protected fields read-only.

**Persisted state, cross-module and negative checks** · Verify scoped metadata changes, valid status pair, audit actor and actual suspended mutation block. Try invalid status/action, no reason, PA viewer, foreign tenant admin and replay. Verify denied state unchanged.

**Evidence** · Directory, confirm/cancel, before/after company and audit, affected tenant traces.

**Acceptance** · PASS requires the sequence, UI, authoritative state and denial assertions to match with evidence. Test with an insufficiently granted and foreign actor wherever the target is tenant or object scoped. Preserve the baseline and isolate fixture failures.

**Baseline references** · apps/organizations/urls.py and the per-row view, permissions and source references in the master inventory. apps/organizations/test_platform_console.py.

<a id="pa-04"></a>

### PA-04 · Manage system user directory and independent accounts

**Batch and status** · B10 · NOT_RUN · 4 worklist rows

**Actors and seed** · PA with users_view/manage, read-only and tenant-only controls. Active, disabled and multi-member accounts, unique synthetic username/recovery email

**Browser sequence** · Search, filter company/status and paginate. Create account; edit allowed names/phone, inspect detail, membership list and recent activity. Attempt to alter read-only username/email.

**Expected UI** · One row per account, effective role and status label clear. Tenant role names visible only with target tenant rights.

**Persisted state, cross-module and negative checks** · Compare User, approved fields, exact directory counts and platform audit. Confirm no tenant membership, staff, or platform role created. Probe duplicate recovery email, forged privileged fields and missing manage permission.

**Evidence** · Directory/filter and detail captures, account/audit snapshots with contacts redacted.

**Acceptance** · PASS requires the sequence, UI, authoritative state and denial assertions to match with evidence. Test with an insufficiently granted and foreign actor wherever the target is tenant or object scoped. Preserve the baseline and isolate fixture failures.

**Baseline references** · apps/organizations/urls.py and the per-row view, permissions and source references in the master inventory. apps/accounts/test_platform_users.py.

<a id="pa-05"></a>

### PA-05 · Deactivate and reactivate account while protecting owners and operators

**Batch and status** · B10 · NOT_RUN · 3 worklist rows

**Actors and seed** · PA with users_manage, ordinary target, protected target. Two active sessions and old reset token, separately last PA, last owner, staff, blocked and self fixtures

**Browser sequence** · Deactivate eligible account with reason, confirm old sessions/login denied. Reactivate, authenticate freshly and retry previous session/token. Use cancel and repeated POST.

**Expected UI** · Confirmations, effective state and failure message clear. Protected account actions unavailable or denied.

**Persisted state, cross-module and negative checks** · Check active flag, auth revision and audit. Probe last effective PA/owner (active or suspended company), technical duties, staff/superuser, blocked state and self. Check denied changes preserve sessions and rows.

**Evidence** · Status/audit timeline and masked session/token results.

**Acceptance** · PASS requires the sequence, UI, authoritative state and denial assertions to match with evidence. Test with an insufficiently granted and foreign actor wherever the target is tenant or object scoped. Preserve the baseline and isolate fixture failures.

**Baseline references** · apps/organizations/urls.py and the per-row view, permissions and source references in the master inventory. apps/accounts/test_platform_users.py.

<a id="pa-06"></a>

### PA-06 · Recover account by email or temporary password

**Batch and status** · B10 · NOT_RUN · 6 worklist rows

**Actors and seed** · PA with users_recover, eligible target, read-only PA. Isolated captured mail, no-SMTP and failing test transport, old credential/tokens

**Browser sequence** · Request reset from user detail, consume link in isolated browser, test cooldown/failed transport. Use temporary password path and authenticate target; verify forced change confinement and final credential.

**Expected UI** · Delivery state distinguishes unavailable/failed/accepted. Fields never echo passwords. No navigation past required change.

**Persisted state, cross-module and negative checks** · Verify stored email recipient, eligibility and protected actor guards, hash/auth revision/force-change flags and audit without secrets. Probe wrong actor, no CSRF, expired/used link, mismatch and weak password.

**Evidence** · Redacted mail envelope/state, success/error screen and masked audit/session checks.

**Acceptance** · PASS requires the sequence, UI, authoritative state and denial assertions to match with evidence. Test with an insufficiently granted and foreign actor wherever the target is tenant or object scoped. Preserve the baseline and isolate fixture failures.

**Baseline references** · apps/organizations/urls.py and the per-row view, permissions and source references in the master inventory. apps/accounts/test_platform_users.py.

<a id="pa-07"></a>

### PA-07 · Grant and revoke Platform Admin duty independently

**Batch and status** · B10 · NOT_RUN · 3 worklist rows

**Actors and seed** · PA with operator permission, eligible active target and tenant-only actor. Two effective PA accounts, independent eligible target, revoked/expired assignment history

**Browser sequence** · Open Administrators, grant duty with reason, re-login as target, then revoke as authorized different actor and retry workspace access.

**Expected UI** · Effective vs historical assignment states and confirm prompt clear. Target receives only authorized platform scope.

**Persisted state, cross-module and negative checks** · Verify PlatformRoleAssignment active/revoked history, actor, reason and audit. Probe self-grant/revoke, last effective PA, inactive target, duplicate duty and tenant admin attempting same POST.

**Evidence** · Role/audit rows and positive/negative menu access.

**Acceptance** · PASS requires the sequence, UI, authoritative state and denial assertions to match with evidence. Test with an insufficiently granted and foreign actor wherever the target is tenant or object scoped. Preserve the baseline and isolate fixture failures.

**Baseline references** · apps/organizations/urls.py and the per-row view, permissions and source references in the master inventory. apps/organizations/test_platform_console.py.

<a id="pa-08"></a>

### PA-08 · Separate role definitions from scoped tenant delegation

**Batch and status** · B10 · NOT_RUN · 3 worklist rows

**Actors and seed** · PA role manager, PA with explicit target tenant permission, PA-only, tenant admin. Global role, tenant A/B custom roles, permission version and independent approver

**Browser sequence** · Read/edit permitted role catalog definition, test stale version. Inspect member roles, select target tenant, attempt grant/revoke with and without explicit target authority. Review independently when configured.

**Expected UI** · Catalog explains scope and impact. Tenant role operations identify target and preserve active tenant session. Platform-only codes absent from tenant grant choices.

**Persisted state, cross-module and negative checks** · Check saved version, grant/revoke and approval chain. Deny forged target membership, self escalation, PA-only and stale update. Verify tenant admin cannot reach platform catalog.

**Evidence** · Role catalog and assignment captures, version/grant/audit diff.

**Acceptance** · PASS requires the sequence, UI, authoritative state and denial assertions to match with evidence. Test with an insufficiently granted and foreign actor wherever the target is tenant or object scoped. Preserve the baseline and isolate fixture failures.

**Baseline references** · apps/organizations/urls.py and the per-row view, permissions and source references in the master inventory. apps/organizations/test_platform_console.py.

<a id="pa-09"></a>

### PA-09 · Verify settings and policy boundaries

**Batch and status** · B10 · NOT_RUN · 3 worklist rows

**Actors and seed** · PA with appropriate policy capabilities, PA read-only, tenant owner. Policy versions and protected-operation catalogs, financial activation absent

**Browser sequence** · Open Settings, inspect displayed profile and follow catalogs. Exercise only actual permitted create/revise/version controls using clone. Try forged profile/sensitive activation write.

**Expected UI** · Settings profile read-only. Existing catalog actions and reason/version fields clear and safe.

**Persisted state, cross-module and negative checks** · Compare PolicyVersion/protected-operation source and audit. Test wrong authority, stale version and unrelated protected settings. No profile switch or statutory activation by request.

**Evidence** · Settings, catalog snapshots, rejected requests and policy/audit diff.

**Acceptance** · PASS requires the sequence, UI, authoritative state and denial assertions to match with evidence. Test with an insufficiently granted and foreign actor wherever the target is tenant or object scoped. Preserve the baseline and isolate fixture failures.

**Baseline references** · apps/organizations/urls.py and the per-row view, permissions and source references in the master inventory. apps/organizations/test_platform_console.py.

<a id="pa-10"></a>

### PA-10 · Filter platform audit and qualify dependency status

**Batch and status** · B10 · NOT_RUN · 2 worklist rows

**Actors and seed** · PA audit/health, PA without individual grants, local admin. Known global and tenant-only events; healthy and simulated dependency/alert-sink states

**Browser sequence** · Filter activity by actor/date/action/company and paginate. Open status under healthy, failed dependency and missing sink conditions using isolated test harness.

**Expected UI** · Only allowlisted events and sanitized results. Unverified sources and service reachability explicit. No raw error/metadata.

**Persisted state, cross-module and negative checks** · Compare actor, time, action and scope with AuditEvent projection. Validate safe probes and no unrelated tenant payload or write. Deny unprivileged access.

**Evidence** · Filtered pages, sanitized probe traces and audit reconciliation.

**Acceptance** · PASS requires the sequence, UI, authoritative state and denial assertions to match with evidence. Test with an insufficiently granted and foreign actor wherever the target is tenant or object scoped. Preserve the baseline and isolate fixture failures.

**Baseline references** · apps/organizations/urls.py and the per-row view, permissions and source references in the master inventory. apps/organizations/test_platform_console.py.

<a id="pa-11"></a>

### PA-11 · Prove separation between platform and tenant authority

**Batch and status** · B10 · NOT_RUN · 33 worklist rows

**Actors and seed** · PA-only, PA+target membership, tenant owner, revoked PA, anonymous. Two tenants and actors with deliberately split grants

**Browser sequence** · Try tenant data list, detail, export and mutation as PA-only, then add only explicit narrow tenant access in fixture. Reverse test all Platform rows as tenant owner and anonymous. Replay revoked actor.

**Expected UI** · Menu, direct URL and action responses align with current authority. Metadata exceptions are scoped to administrative surfaces.

**Persisted state, cross-module and negative checks** · Compare session, role assignments, permissions and unchanged snapshots for rejected requests. Check technical Django Admin denial in MVP and separate underlying gate in FULL_ERP.

**Evidence** · Actor/route/method result matrix and no-side-effect evidence.

**Acceptance** · PASS requires the sequence, UI, authoritative state and denial assertions to match with evidence. Test with an insufficiently granted and foreign actor wherever the target is tenant or object scoped. Preserve the baseline and isolate fixture failures.

**Baseline references** · apps/organizations/urls.py and the per-row view, permissions and source references in the master inventory. apps/organizations/test_platform_console.py.
