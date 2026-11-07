# Equipment selectors and Maintenance Create remediation

Status: ready for visual review; no Product Owner acceptance claimed.
Branch `main`, HEAD `59f2fde64fc3684f09871b82a2b1945905c28aab`.
No commit or push. Existing uncommitted work was preserved; entry hashes and
source snapshots are in `entry.json` and `*.before`.

## Delivered

- Equipment List: ownership's empty choice now reads **نوع مالکیت**. Category is
  a select populated from unarchived equipment in the authorized organization
  queryset, with **همه دسته‌های تجهیز** as its empty choice. Existing category
  substring filtering, including legacy partial-text URLs, is preserved. Search,
  status, sort, pagination, export and context are unchanged.
- Equipment Create: category uses the existing shared Tom Select assets as an
  editable searchable dropdown. It suggests only the active tenant's unarchived
  equipment categories and accepts new text, as the existing CharField/service
  already did. No new category master, fixed taxonomy or relationship is invented.
  The native datalist works without JavaScript. Required/max-length validation,
  escaping, selected values and text containing commas are retained. New text
  creation is opt-in for this input; relationship selects remain non-creatable.
- Maintenance Create: existing fields now use the approved Sectioned Form pattern:
  service identity/schedule; project/site/provider; work description/cost/notes.
  Reuses the common header/context, section headers, field/error rendering and one
  in-flow Save/Cancel footer. Original POST fields, choices, service, validation,
  scope and success/cancel destinations are unchanged. Other equipment operational
  forms retain their own layouts.
- Materials, Material Categories and Equipment lists already use the same shared
  `operational_list.html` as Safety. That existing implementation was preserved
  and its browser/navigation/filter/permission regressions rerun.
- Daily Report Create already contains the authorized related Safety/Quality and
  DMS selectors plus existing document-upload controls, alongside the original
  notes. The existing reference service and its actual browser submission,
  retention, scoped access and rollback tests were rerun. No duplicate association
  mechanism was added.

## Exact incremental files

1. `apps/equipment/forms.py`: tenant-scoped editable category widget/suggestions;
   keeps the original CharField validation.
2. `apps/equipment/views.py`: list category options/labels, active organization
   passed to EquipmentForm, dedicated Maintenance Create template.
3. `apps/equipment/templates/equipment/widgets/category_selector.html`: native
   input/datalist fallback inside the existing shared choice wrapper.
4. `apps/workforce/static/workforce/field_choices.js`: opt-in local editable text
   enhancement; explicitly retains the whole initial value, including commas.
5. `apps/accounts/templatetags/reference_lists.py`: optional per-column empty label,
   with existing defaults preserved for other lists.
6. `apps/accounts/templatetags/form_layouts.py`: maintenance presentation profile.
7. `templates/equipment/maintenance_create.html`: shared Sectioned Form consumer.
8. `docs/ui-guidelines.md`: documents maintenance adoption and editable-text boundary.
9. `scripts/verification/mvp02_browser.mjs`: optional input selector/new-choice
   support for real typed-and-clicked Chrome dropdown verification.
10. `tests/test_equipment_selector_remediation.py`: focused functional/browser suite.

Evidence is in this directory. The prior Record Detail continuation added
`tests/test_record_detail_document_states.py` and its own report/evidence under
`output/detail-page-rollout/follow-up/`; it required no product-code changes.
All other current dirty files belong to earlier/concurrent work and are not
attributed to this remediation.

## Browser and functional verification

[Screenshot gallery](gallery.html): actual Chrome viewport, genuine full-page and
bottom screenshots at **1440, 1024 and 390px** for Equipment List, Equipment Create
and Maintenance Create. Synthetic data in the existing isolated PostgreSQL test
database; no development business records were created by these tests.

Equipment-specific evidence covers 17 distinct successful Chrome scenarios:
existing category search/selection, new category submission, retained value after
invalid POST (including a comma), no-JavaScript save, tenant-private options,
ownership/category composition, active chips, Clear, Back/Forward, refresh, empty
results, native GET filtering, Sectioned Form validation/value retention, actual
maintenance submission and Cancel. It also checks denied Create access and invalid
project/site combinations. RTL, no page horizontal overflow and no JavaScript
exceptions are checked by the existing browser driver.

Related regression suites cover list sort/pagination/tenant isolation, matching
list structure against actual Safety rendering, navigation and real daily-report
HSE/document association behavior. Successful final logs supersede earlier test
iterations. An initial category-retention failure exposed the widget's missing
initial-value option; it was corrected and rerun. That failure log is preserved.

Final results: **15 tests PASS, 4 subtests PASS**, covering all three focused
Equipment methods, the list/navigation suite and the daily-reference suite.
See `verified-tests.txt` and `verified-tests.xml`. Earlier `final-tests.txt` had
14 PASS before adding the category-retention/native-save regression; the final
aggregate includes it. `ruff.txt`, JavaScript syntax checks, Django system check
and schema drift check pass (`system-check.txt`, `schema-check.txt`). The AST
comparison in `source-contract-check.json` confirms unchanged Equipment field
declarations, unchanged MaintenanceRecordForm and unchanged equipment/maintenance
business service call contracts. The selector enhancement uses existing installed
assets; no frontend dependency or page-specific CSS was added.

## Limits

- UI/layout/widget changes only: no new models, migrations, business rules,
  workflows, permissions, tenant/project scope or Product Surface changes.
- Equipment category remains the existing text value; governing a fixed taxonomy
  or introducing a Category model would be a separate product/domain change.
- Native browser file chooser/date-picker language and physical mobile keyboards
  are outside these viewport-emulation checks. No screen-reader certification.
- `manage.py migrate --check` reports the unrelated existing pending migration
  `payroll.0010_cep069_reviewed_statutory_context`. It was not executed. The daily
  report reference migrations are already applied in the development database.
- Product Owner visual acceptance remains pending. No commit or push.
