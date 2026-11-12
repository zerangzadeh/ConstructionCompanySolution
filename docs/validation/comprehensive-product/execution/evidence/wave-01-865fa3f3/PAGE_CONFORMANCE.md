# Rendered page design dispositions

These results concern the inspected design states. Per-route functional, business, navigation, authorization and PO dispositions are in the MVP matrix. Representative responsive and screenshot comparisons are combined with the current rendered structure and interactions. Some overlays on the same URL are listed separately.

| Observed page or state | Archetype | CSS widths | Design result | Browser evidence |
|---|---|---|---|---|
| login | DC-01 | 390, 1024, 1440 | NEEDS_PO_REVIEW · REFERENCE_MISSING | [browser-all.json](browser-all.json) |
| login-invalid | DC-01/DC-09 | 1440 | NEEDS_PO_REVIEW · REFERENCE_MISSING | [browser-all.json](browser-all.json) |
| tenant-selector | DC-03/DC-09 | 1440 | PASS · scoped matrix criteria | [browser-all.json](browser-all.json) |
| tenant-home | DC-02/DC-08 | 1440 | PASS · scoped matrix criteria | [browser-all.json](browser-all.json) |
| global-search | DC-02/DC-03 | 1440 | PASS · scoped matrix criteria | [browser-all.json](browser-all.json) |
| project-detail | DC-03/DC-05 Projects exception | 1440 | NOT_RUN for full conformance · rendered observation retained | [browser-all.json](browser-all.json) |
| restricted-home | DC-02/DC-08 | 1440 | PASS · scoped matrix criteria | [browser-all.json](browser-all.json) |
| restricted-menu | DC-02/DC-03 | 390, 1024, 1440 | PASS · scoped matrix criteria | [browser-all.json](browser-all.json), [browser-retry-auth.json](browser-retry-auth.json) |
| required-password | DC-06/DC-09 | 1440 | PASS · scoped matrix criteria | [browser-all.json](browser-all.json) |
| public-reset | DC-01/DC-09 | 1440 | NEEDS_PO_REVIEW · REFERENCE_MISSING | [browser-all.json](browser-all.json) |
| public-reset-done | DC-01/DC-09 | 1440 | NEEDS_PO_REVIEW · REFERENCE_MISSING | [browser-all.json](browser-all.json) |
| public-reset-confirm | DC-01/DC-09 | 1440 | NEEDS_PO_REVIEW · REFERENCE_MISSING | [browser-all.json](browser-all.json) |
| public-reset-complete | DC-01/DC-09 | 1440 | NEEDS_PO_REVIEW · REFERENCE_MISSING | [browser-all.json](browser-all.json) |
| platform-dashboard | DC-02/DC-08 | 390, 1024, 1440 | PASS · scoped matrix criteria | [browser-all.json](browser-all.json) |
| platform-companies | DC-04/DC-10 | 1440 | NEEDS_PO_REVIEW · REFERENCE_MISSING | [browser-all.json](browser-all.json) |
| platform-company-detail | DC-05/DC-10 | 1440 | NEEDS_PO_REVIEW · REFERENCE_MISSING | [browser-all.json](browser-all.json) |
| platform-company-create | DC-07/DC-10 | 1440 | PASS · scoped matrix criteria | [browser-all.json](browser-all.json) |
| platform-company-edit | DC-07/DC-10 | 1440 | PASS · scoped matrix criteria | [browser-all.json](browser-all.json), [browser-company-edit.json](browser-company-edit.json), [browser-retry-platform.json](browser-retry-platform.json) |
| platform-users | DC-04/DC-10 | 390, 1024, 1440 | PASS · scoped matrix criteria | [browser-all.json](browser-all.json) |
| platform-user-detail | DC-05/DC-10 | 390, 1024, 1440 | PASS · scoped matrix criteria | [browser-all.json](browser-all.json) |
| platform-user-create | DC-06/DC-10 | 1440 | PASS · scoped matrix criteria | [browser-all.json](browser-all.json) |
| platform-user-edit | DC-06/DC-10 | 1440 | PASS · scoped matrix criteria | [browser-all.json](browser-all.json) |
| platform-user-temp | DC-06/DC-09/DC-10 | 1440 | PASS · scoped matrix criteria | [browser-all.json](browser-all.json), [browser-retry-platform.json](browser-retry-platform.json), [browser-secure-platform.json](browser-secure-platform.json) |
| platform-admins | DC-11 | 1440 | PASS · scoped matrix criteria | [browser-all.json](browser-all.json) |
| platform-roles | DC-11 | 1440 | PASS · scoped matrix criteria | [browser-all.json](browser-all.json) |
| platform-member-roles | DC-11 | 1440 | FAIL · BON-DEF-0001 | [browser-all.json](browser-all.json) |
| platform-member-authorization | DC-11 | 1440 | NOT_RUN for full conformance · rendered observation retained | [browser-all.json](browser-all.json) |
| platform-role-create | DC-11 | 1440 | NOT_RUN for full conformance · rendered observation retained | [browser-all.json](browser-all.json) |
| platform-settings | DC-11 | 1440 | PASS · scoped matrix criteria | [browser-all.json](browser-all.json) |
| platform-protected | DC-11 | 1440 | FAIL · BON-DEF-0003 | [browser-all.json](browser-all.json) |
| platform-policy | DC-11 | 1440 | PASS for observed design; policy lifecycle coverage pending | [browser-all.json](browser-all.json) |
| platform-audit | DC-11 | 1440 | FAIL · BON-DEF-0002 | [browser-all.json](browser-all.json) |
| platform-status | DC-11 | 1440 | PASS · scoped matrix criteria | [browser-all.json](browser-all.json) |
| platform-audit-date | DC-11/DC-09 | 1440 | FAIL · BON-DEF-0002 | [browser-audit-date.json](browser-audit-date.json), [browser-catalog-audit.json](browser-catalog-audit.json) |
| delegate-member-authority | DC-11 | 1440 | PASS · scoped matrix criteria | [browser-delegate.json](browser-delegate.json) |
| member-selector-accessible | DC-11/DC-09 | 1440 | FAIL · BON-DEF-0001 | [browser-design-review.json](browser-design-review.json) |
| public-reset-expired | DC-01/DC-09 | 1440 | NEEDS_PO_REVIEW · REFERENCE_MISSING | [browser-expired-auth.json](browser-expired-auth.json) |
| personal-settings | DC-03/DC-06 | 1440 | PASS · scoped matrix criteria | [browser-retry-auth.json](browser-retry-auth.json) |
| viewport-companyList | DC-04/DC-10 | 390, 1024 | NEEDS_PO_REVIEW · REFERENCE_MISSING | [browser-viewport-review.json](browser-viewport-review.json) |
| viewport-companyDetail | DC-05/DC-10 | 390, 1024 | NEEDS_PO_REVIEW · REFERENCE_MISSING | [browser-viewport-review.json](browser-viewport-review.json) |
| viewport-companyEdit | DC-07/DC-10 | 390, 1024 | PASS · scoped matrix criteria | [browser-viewport-review.json](browser-viewport-review.json) |
| viewport-userCreate | DC-06/DC-10 | 390, 1024 | PASS · scoped matrix criteria | [browser-viewport-review.json](browser-viewport-review.json) |
| viewport-roles | DC-11 | 390, 1024 | PASS · scoped matrix criteria | [browser-viewport-review.json](browser-viewport-review.json) |
| viewport-members | DC-11 | 390, 1024 | FAIL · BON-DEF-0001 | [browser-viewport-review.json](browser-viewport-review.json) |
| viewport-settings | DC-11 | 390, 1024 | PASS · scoped matrix criteria | [browser-viewport-review.json](browser-viewport-review.json) |
| viewport-audit | DC-11 | 390, 1024 | FAIL · BON-DEF-0002 | [browser-viewport-review.json](browser-viewport-review.json) |
| viewport-status | DC-11 | 390, 1024 | PASS · scoped matrix criteria | [browser-viewport-review.json](browser-viewport-review.json) |
