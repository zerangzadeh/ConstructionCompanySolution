# B06 inbound transfers enhancement

**12 November 2026 · MVP · Product Owner decision approved · Formal acceptance pending**

The Product Owner approved **«انتقال‌های ورودی در انتظار دریافت»** within the Inventory Custody Workbench. Receivers can open it from **انبارها**. A receiving role without warehouse-list permission can enter the same workbench through **کنترل موجودی** in the shared navigation. The pending tab lists in-transit transfers for authorized destinations, excludes the dispatcher's own transfers, and shows the reference, source and destination, tenant-local Jalali dispatch date, item summary, and status. Receivers can search by reference or warehouse name, filter by destination, and choose **«مشاهده و دریافت»** to use the existing acceptance form. The **سوابق انتقال** tab retains accepted transfers in destination scope.

The workbench uses the existing transfer view and acceptance permissions and destination-project grants. Company-wide custody summaries retain their existing permission checks. The detail preserves its workbench return link through acceptance, and the stock and audit services retain their existing behavior. No schema change was needed.

| Verification | Result |
|---|---|
| Chrome 156 at 1440, 1024 and 390 CSS px | Discovered the pending tab from the warehouse list. Reference search, searchable destination filter, Persian empty state, status, actions and Jalali dates passed. Reviewed the desktop table and narrow cards. |
| Scope and direct requests | The source-only actor had an empty pending list and could still read its own outbound detail. Acceptance returned 404. The sibling-project and foreign-tenant actors could neither view nor accept the target. A forged destination filter returned no rows. The destination receiver's source-side actions returned 404. |
| Acceptance, replay and history | Chrome accepted 3 units through the existing form. The transfer left pending and appeared in history. Independent PostgreSQL readback found one 3-unit dispatch, one 3-unit receipt, separate actors, four lifecycle audit events and zero journal entries. |
| Focused PostgreSQL regression | 43 tests and 17 subtests passed, including the existing B06 custody and transfer tests, the transfer-dispatch race, and shared navigation and Product Surface tests. |
| Database and repository checks | The isolated PostgreSQL 18.6 base recorded 462 migrations and zero tenants. Migration and drift checks found no pending changes. Django, targeted Ruff, and diff checks passed. |

[Chrome assertions](evidence/b06-inbound-enhancement/chrome/observations.json) · [1440 px](evidence/b06-inbound-enhancement/chrome/inbound-1440.png) · [1024 px](evidence/b06-inbound-enhancement/chrome/inbound-1024.png) · [390 px](evidence/b06-inbound-enhancement/chrome/inbound-390.png) · [Transfer history](evidence/b06-inbound-enhancement/chrome/history-1440.png) · [Read-only PostgreSQL witness](evidence/b06-inbound-enhancement/persisted-postgres.json) · [Focused test results](evidence/b06-inbound-enhancement/http-final.log)

The historical B06 closeout remains **88/88 PASS**, with the original outcomes retained separately. The shared matrix received concurrent changes. All 88 B06 execution IDs, statuses and observations matched the prior witness. The enhancement ran against synthetic data in isolated PostgreSQL clones and preserved existing business data. No commit, push, or production operation occurred. [Historical B06 report](B06_EXECUTION_REPORT.md) · [Preservation witness](evidence/b06-inbound-enhancement/history-preservation.json)
