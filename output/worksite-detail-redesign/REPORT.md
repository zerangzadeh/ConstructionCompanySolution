# Worksite Detail UI review

Reviewed on 2026-11-11 from local `main` at `865fa3f3f7868e81b0aafba05d2683b28fe33b1e`, aligned with `origin/main`. The working tree contained existing work before this task.

The page now has a short description, a compact four-field overview, and icon-labelled Workforce and Timekeeping actions with 44px targets. Workforce receives primary emphasis when available. The first authorized action receives emphasis when only one action is available. The overview contains the existing site code, parent project, status and address once each.

Presentation follows `docs/ui-guidelines.md` and the supplied images. The existing record-detail shell, summary items, status badge, icons and application context provide the layout. Existing navigation callers retain their secondary-button presentation. A stylesheet version update resolves stale cached action styles observed during browser verification.

## Changed files

- `apps/projects/templates/projects/site_detail.html`
- `apps/projects/test_site_detail_presentation.py`
- `apps/workforce/templatetags/field_journey.py`
- `apps/workforce/templates/workforce/_journey_links.html`
- `apps/accounts/static/css/erp_record_detail.css`
- `templates/components/record_detail_page.html`

Earlier edits to the site view, list pages and boundary tests were already present when this redesign began. Other working-tree changes were preserved. Changes remain uncommitted on `main`.

## Browser evidence

Chrome verification used the active worksite in ساختمان اداری آفتاب at `/projects/623b4e02-b751-495f-b0e7-7e1601b9ccdf/sites/4f195bba-4013-4cb3-acfa-53edfb3ef357/`.

| Width | Before | After | Result |
| --- | --- | --- | --- |
| 1440px | [Before](before-1440.jpg) | [After](after-1440.jpg) | PASS |
| 1024px | [Before](before-1024.jpg) | [After](after-1024.jpg) | PASS |
| 390px | [Before](before-390.jpg) | [After](after-390.jpg) | PASS |

Screenshots show the content and visible sidebar. The application profile area is excluded. Desktop captures are 475px high and the mobile capture is 570px high.

- All widths show the correct site code, parent project, active status and address, with one page title and one shared working-context control.
- The overview has four populated columns at 1440px and 1024px and one column at 390px. All widths have zero page-level horizontal overflow.
- Both actions appear once, use decorative icons and have measured 44px target heights.
- Workforce and Timekeeping were opened successfully. Their destination selectors retained the exact project and site. Browser Back returned to Site Detail.
- Keyboard Tab moved from Workforce to Timekeeping with a visible focus outline. Enter opened Timekeeping successfully.
- A site URL paired with a mismatched project returned 404 and rendered no site overview.

## Automated verification

- `python -m pytest apps/projects/test_site_detail_presentation.py --reuse-db -q --tb=short` passed with 6 tests and 7 subtests. Coverage includes active/inactive status, blank address, all action-permission combinations, compatibility with existing journey callers, GET-only behavior, tenant isolation, project scope, mismatched parents and members without scope grants.
- A broader run of four selected tests in `core/test_list_detail_resolution.py` reported 3 passed, 5 failed and 5 subtests passed. All five failures originate in existing Timekeeping cases whose fixture lacks `OrganizationSettings`. `apps/timekeeping/views.py` fails at line 57 while resolving the organization timezone, before template rendering. These are unrelated failures in the pre-existing working tree. Dedicated Site Detail boundary tests pass against the isolated PostgreSQL test database.
- `python manage.py check` passed with zero issues.
- `python manage.py findstatic css/erp_record_detail.css --verbosity 0` resolved the shared stylesheet.
- Ruff lint passed for both affected Python files. Formatting passed for the new test file and changed journey code. Whole-file formatting identifies existing debt in unrelated functions in `field_journey.py`; those functions match the original source.
- `git diff --check` passed.
- Six JPEG files were inspected and their dimensions verified.

## Review limits

The browser account had access to both navigation destinations. Restricted combinations, inactive/blank-address presentation and site access boundaries are covered by automated tests. A later attempt to additionally inspect the originally reported worksite was blocked when local browser use became disabled in Work settings.

The existing Timekeeping fixture failures and unrelated whole-file formatting debt remain recorded above.

Product Owner visual review remains pending.
