# CEP-053 Execution Manifest

## Before product mutation â€” 2026-10-18

Clean `main` / `origin/main` / remote at
`a383df06cc90860fe0c778a705617b94dd356c33`. CEP-052 direct integration is
reconciled separately from execution. All 79 canonical prompt hashes were checked
at bootstrap; CEP-053 hash is
`6e2eb63215509c29bbd5c221ad82dbf244e6ab5b9294152c8d0704aa99890bc5`.
CEP-017 and CEP-026 COMPLETE; GATE-02 PASS. Standing bounded non-production
authority applies. Six AC; scoped DoD; unit/service/permission/tenant/workflow/UI
and affected regression plus screenshots required. Migration NONE.

Recovered canonical sources: frozen PD-025/029; SPEC-014 completed ESS field policy;
ESS functional specification ESS-CAP-001/002 and WS-03/UI architecture. They allow
own-data composition and source links, never authoritative profile edits, a new
permission codename, dashboard KPI, management scoring or unsupported data shown
as zero. My Tasks/My Requests/Manager handling remain distinct. Existing CEP-026
profile/subject authority and CEP-018 My Requests read model are reused. No new
identity inference or domain state is introduced. Unsupported Payroll/leave balance/
notification/etc. adapters are omitted; downstream CEPs own them.

Actual intended product touch set: new `apps/workforce/ess_dashboard.py` composition
service; `apps/workforce/views.py` thin GET dashboard; `apps/workforce/urls.py` ESS
landing; `templates/workforce/ess_dashboard.html` and shared ESS navigation include;
existing `templates/workforce/ess_profile.html` includes the shell; shared
`templates/components/navigation_links.html` NAV-006 points to the landing;
`apps/workforce/test_cep053.py` verifies own-source composition, strict current
Person/WorkRelationship-to-legacy-source bridge, permissions, raw statuses,
unavailable/empty/error states, cross-tenant denial, read-only methods and Persian/
RTL/Jalali. No model, migration, data movement, new permission, profile field edit,
request workflow, manager action or source mutation.

Governance touch set: this manifest, CEP-053 acceptance/evidence/change CSVs,
screenshots, completion report, root Registry. Capture screenshots only from
authorized synthetic test responses; broad browser/accessibility and performance
runtime remain UTV. Recompute frontier after completion; no production authority.

Baseline: 12/12 ESS privacy and personal-workspace regression tests PASS. The
CEP-026 navigation assertion will follow NAV-006 to the new dashboard; its source
profile authorization and masking assertions remain unchanged. This adds only
`apps/workforce/test_cep026_ess_privacy.py` navigation-target assertions to the
actual touch set before that test mutation.

Required unauthorized-state UI adds `templates/workforce/ess_unavailable.html`
and local ESS view handling before mutation: the existing generic Django 403 is
English. The scoped template gives one Persian non-disclosing response for missing
or unauthorized identity/profile objects. Shared/global error policy is unchanged.

## Validation closeout

19 final tests PASS. The localized denial page is rendered without request context
so foreign/nonexistent object responses remain byte-identical despite the shared
shell's CSRF forms. The initial test rejecting all forms was narrowed to profile
edit fields; shared search/logout stay intact. Ruff/check/drift/whitespace PASS.
Five inspected screenshots cover ready, empty, error, Persian denial and true
390x900 mobile emulation. Desktop CLI capture was sufficient; mobile CLI minimum
width was replaced using Chrome device emulation. Measured viewport/document/main
widths are 390. No live tenant data, migration, new KPI or domain mutation.
