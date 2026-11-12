# B10 Platform Admin

**Baseline** · main at `865fa3f3f7868e81b0aafba05d2683b28fe33b1e`, matching local origin/main. MVP, real Google Chrome 156.0.8078.80 and disposable PostgreSQL 18. Wave run dated 2026-11-10 Asia/Tehran.

| Planned | Rows with evidence | PASS | FAIL | BLOCKED | NOT_RUN | NEEDS_PO_REVIEW | PO_ACCEPTED |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 66 | 66 | 60 | 3 | 0 | 1 | 2 | 0 |

The NOT_RUN policy catalog row has partial evidence. Full draft, review, publication and retirement remain pending. Each authorization-only row tests the denied operation. Positive page, navigation and mutation results are recorded in the corresponding primary row.

| Journey | Verified through the browser and technical witnesses |
|---|---|
| PA-01 Dashboard | Real Platform-only sign-in and eight destinations. Chrome dashboard showed five companies, 36 accounts and nine memberships, matching the pre-run database witness. KPI grid, status, activity, quick actions and dependencies checked at 1440/1024/390. |
| PA-02 Onboarding | Rejected initiating administrator as initial owner. Created an isolated company with a distinct owner and both starter workflows. A legacy fixture with one effective owner and missing starters exercised Retry. Persisted company, owner, workflow status and audit reconciled. Dedicated company detail visual reference requires PO review. |
| PA-03 Company management | Search reached exact company; disabled currency stayed read-only, reasoned edit persisted, cancel preserved state, suspension blocked tenant access and reactivation restored active status. Dedicated company list visual reference requires PO review. |
| PA-04 User directory and accounts | Search led to the exact user, creation saved an independent account, and permitted edit returned to its detail. Filter/pagination and protected fields also checked in focused tests. Compared the directory and account detail with their implementation references at the required widths. |
| PA-05 Account lifecycle | Chrome canceled, deactivated and reactivated a synthetic account. Old sessions remained invalid after reactivation; fresh login worked. Focused tests checked protected targets and old tokens. |
| PA-06 Recovery | Unconfigured delivery was disabled with an explanation. Chrome over loopback HTTPS exercised captured SMTP success, refusal, cooldown, stored-recipient link, completion and replay denial. Temporary password required personal initialization and changed the authentication revision. |
| PA-07 Operator management | Granted a separate actor Platform authority, confirmed its workspace access, revoked the grant, and verified immediate denial from the existing session. Read-only snapshot preserved revoked history. |
| PA-08 Roles and delegation | Global role editor created an exact scoped permission set. Platform-only actor could not inspect member grants. A dual-authority actor assigned and revoked Viewer through real forms with a distinct authorized approver. The company chooser exposed an unnamed duplicate combobox (BON-DEF-0001). |
| PA-09 Settings and catalogs | Read-only MVP profile and both catalog links verified. Synthetic insurance classification persisted. Protected operation version 2 was created and retired while retaining history. A single click performed the retirement without confirmation (BON-DEF-0003). Full policy publication lifecycle remains open. |
| PA-10 Audit and status | Combined company, actor and Jalali date filters returned two matching events. Gregorian field labels conflict with the actual Jalali control (BON-DEF-0002). Current status showed dependencies; focused fault tests covered missing alert source and sanitized dependency failure. Audit action filter and pagination have no dedicated browser result. |
| PA-11 Separation | All 23 Platform URL declarations returned 403 to a tenant owner and redirected anonymous requests to login. Mutable paths also rejected authenticated tenant-owner POSTs. Platform-only session was redirected away from tenant project reads and export; explicit target membership enabled only the governed delegation tested. |

## Design conformance

DC-02, DC-03 and DC-08 cover the Platform shell, dashboard, navigation and target context. DC-04/DC-05/DC-10 cover company and account lists/details; the company-specific visual reference gap remains. DC-06/DC-07/DC-09 cover account, company and credential forms, required reason, confirm/cancel and feedback. DC-11 covers roles, settings, audit, status and protected catalogs. The scoped results for each rendered page and the responsive observations are in the browser JSON and matrix. The three confirmed deviations are [registered defects](../DEFECT_REGISTER.md). A documented status, history or reference gap remains distinct from a functional or business-rule result.

The [page conformance index](evidence/wave-01-865fa3f3/PAGE_CONFORMANCE.md) separates adjudicated states from rendered observations that still need full conformance checks. The [responsive follow-up](evidence/wave-01-865fa3f3/browser-viewport-review.json) measured nine representative Platform screens at 1024 and 390 without page-level overflow.

No business-state or authorization failure was observed in the tested Platform operations. The initial HTTP temporary-password 403 was the secure-transport guard, confirmed by the later successful HTTPS run. Earlier fixture and selector failures are retained in the evidence and superseded by targeted runs. Historical Platform implementation captures remain evidence of the corresponding page designs. None of the three new defects matches an existing finding closely enough to reopen it.

**PO review.** Identify approved company list/detail visual references and decide the treatment of the three confirmed findings. No acceptance was recorded.

Evidence · [Browser run](evidence/wave-01-865fa3f3/browser-all.json) · [Onboarding retry](evidence/wave-01-865fa3f3/browser-retry-platform.json) · [Company edit](evidence/wave-01-865fa3f3/browser-company-edit.json) · [Secure password](evidence/wave-01-865fa3f3/browser-secure-platform.json) · [SMTP and recovery](evidence/wave-01-865fa3f3/browser-secure-recovery.json) · [Delegation](evidence/wave-01-865fa3f3/browser-delegate.json) · [Chooser accessibility](evidence/wave-01-865fa3f3/browser-design-review.json) · [Audit date controls](evidence/wave-01-865fa3f3/browser-audit-date.json) · [Protected retirement](evidence/wave-01-865fa3f3/browser-catalog-audit.json) · [Focused tests](evidence/wave-01-865fa3f3/test.log) · [Final database witness](evidence/wave-01-865fa3f3/state-final.json)
