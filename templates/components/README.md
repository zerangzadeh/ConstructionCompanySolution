# Template component conventions

These conventions support the complete Construction ERP product and its
production-oriented quality target rather than a temporary MVP interface.
Components should therefore be durable, accessible, responsive,
Persian/RTL-safe, and reusable across product domains without weakening
server-side boundaries.

Shared Django template fragments belong in this directory when they represent a
stable, reusable UI pattern. Components must receive all required context
explicitly through `{% include ... with ... only %}` so that their dependencies
remain clear and they do not accidentally rely on tenant or request state.

- `form_errors.html` renders non-field validation errors for one bound form.
- `form_field.html` renders one labelled Django form field and its errors.
- `messages.html` renders Django's framework messages from the shared context
  processor.
- `navigation_links.html` renders shared module links. Pass
  `navigation_is_authenticated`, `navigation_link_class`,
  `navigation_primary_class`, and `csrf_token` explicitly; it supports both
  the desktop and mobile navigation layouts in `base.html`.
- `page_header.html` renders a page eyebrow, title, optional description, and
  optional primary action. Pass `page_eyebrow`, `page_title`,
  `page_description`, `page_action_url`, and `page_action_label` explicitly.

Keep business decisions, authorization checks, and formatting of financial
values outside components. Components are presentation-only and must preserve
server-side validation as the source of truth.

## Reference List foundation (Contracts adoption only)

`contracts/list.html` opts into `css/erp_reference_list.css`. This is the first
Reference List implementation; adoption by other modules needs separate scope
and Product Owner review. No JS/CSS dependency has been added.

- `filter_bar.html` accepts `bar` from `core.list_filters.build_filter_bar`.
  Search, quick fields, advanced fields, errors and GET state stay server-owned.
  `erp_filter_bar.js` enhances native disclosures; all fields work without JS.
- `list_active_filters.html` accepts `bar`, renders individually removable chips
  and clear-all when applicable. The helper retains verified inherited context
  and sort state while resetting pagination.
- `list_result_summary.html` accepts `bar`, renders the full filtered result
  count independently from the page length. It never computes business totals.
- `list_result_toolbar.html` accepts `bar` and optional `sort` with a verified
  business `label` and `descending` flag. It groups the result summary and current
  ordering immediately before the table. It does not add sorting or aggregation.
- The filter enhancement places the single clear-all link next to Apply on
  desktop and restores it to the visible chip group on mobile. Without JavaScript,
  clear-all remains with the chips. Existing GET and context semantics are retained.
- `list_pagination.html` accepts `page_obj`, `pagination_query`, `result_label`.
  It shows the actual range, current page and previous/next controls without
  enumerating every page. Filters and inherited context stay in the query.
- `.erp-responsive-list` is a semantic table at desktop widths, with one DOM row
  per record. Below 1200px, the same rows form cards. Use `data-label` for
  metadata, `.erp-list-identifier` with `<bdi dir="ltr">` for canonical numbers,
  `.erp-list-title` for title/project hierarchy, `.erp-list-status` for status,
  `.erp-list-amount` and `.erp-list-row-action` for amount and existing actions.
  Do not introduce selection or bulk controls without an existing business action.
- `list_working_context.html` accepts the existing authenticated context selector
  inputs explicitly. Its compact native disclosure is independent of page filters.
  Use it only on a list whose verified scope behavior supports that statement.

The `base.html` extension blocks `working_context` and `list_pagination` preserve
the original defaults for every other page. Contract-side wording belongs to
`contracts/side_label.html`; shared components contain no direction semantics.

## Reference Create Form Pattern (Contracts adoption only)

The supplied 2026-11-01 Contract Create image is the visual acceptance reference.
`contracts/create.html` is the reference implementation awaiting Product Owner
visual acceptance; no other Create page adopts this pattern in this change.

- Load `css/bonira_tokens.css` and `css/erp_create_form.css` only on opted-in pages.
  Tokens map the canonical color system without changing the application shell.
- `create_form_header.html` takes `page_title`, `page_description`,
  `page_breadcrumbs`, `organization`, and `form`. The organization must be the
  authenticated active organization. Inherited parents come from the validated
  form. `erp_create_form.js` mirrors the existing qualified project selection
  into the summary using textContent; it never writes form/session state.
- `form_section_header.html` takes a unique `heading_id`, `heading`, optional
  `description`, and `icon`. Associate each enclosing section with that heading.
- `.erp-form-grid--two` / `--three` use equal minmax columns, collapsing to one
  below 640px. `.erp-form-grid__full` spans a row. Follow DOM/tab order in RTL.
- Reuse `form_field.html` and `form_errors.html` unchanged for labels, required
  indicators, server errors and accessible help/error associations. Keep existing
  SearchChoiceSelect/Tom Select, JalaliDateMixin and money helpers authoritative.
- `form_footer.html` takes `submit_label` and the existing view's `cancel_url`.
  The sticky footer retains accessible actions while scrolling. Render only real
  supported operations; Contract Create has no separate draft-save command.
- No fields, validators, tenant/project queries, permissions, workflow or product
  exposure may be inferred from the reference. Further adoption needs explicit
  scope and the page's own browser/functional review.

## Compact Form Reuse Guide

Use this pattern for a simple Create or Edit form with one logical section.
Warehouse Create is the implementation reference. Use the approved [visual reference](../../docs/compact-form-reference.png)
and [layout specification](../../docs/compact-form-specification.png) to review
the form inside the existing application shell.

1. Extend `compact_form_page.html` for the canonical assets, working-context
   disclosure and `.erp-compact-page`. In `compact_content`, use `page_header.html`
   with the existing parent route, title, description and shared icon.
2. Include `compact_form_card.html` for an ordinary bound form. For a custom
   field arrangement, use `.erp-create-form.erp-compact-form`. Include
   the CSRF token and supported hidden fields. Use `form_section_header.html`
   and associate the section with its heading. Inside `.erp-compact-form__body`,
   render `form_errors.html`, then use `.erp-form-grid.erp-form-grid--two` and
   `form_field.html` for the actual bound fields. Use `.erp-form-grid__full` for
   a field that needs a full row. The grid stacks below 640px.
   Pass `form`, `csrf_token`, `cancel_url` and `submit_label` explicitly to the
   card when using `only`. Use `cancel_only=True` for the existing read-only
   view and `server_validation=True` only when the original page used `novalidate`.
3. Keep the form's existing field types, required flags, validation and choice
   scope. A `SearchChoiceSelect` with `data-local-choices="true"` can search a
   complete, already-authorized native option set. For a large or paginated
   option set, use the existing scoped lookup pattern. Render `form.media.css`
   and `form.media.js` when the widgets require them.
4. Place `form_footer.html` after the section within the same form. Pass the
   actual submit label, cancel URL and optional `submit_icon`. The actions sit
   together at the bottom of the card and stack on mobile.
5. Verify the bound form at 1440, 1024 and 390px, including field and non-field
   errors, value retention, keyboard operation, scoped choices, Save and Cancel.
   Each implementation needs its own Product Owner review.

## Sectioned Form Reuse Guide

Extend `sectioned_form_page.html` and supply the existing page header inside
`sectioned_content`. Its shared context header comes from `compact_form_page.html`.
An optional `working_context_note` can explain how the form's own relationships
interact with global context without adding selectors.

Keep the consuming POST form and its CSRF token in the page template. Add
`.erp-create-form.erp-sectioned-form`, include `sectioned_form_fields.html`
with the bound `form` and a named `profile`, and then include `form_footer.html`
with the existing primary label and Cancel URL. Profiles live in
`apps/accounts/templatetags/form_layouts.py` and contain field names and display
headings only. Each visible field appears once. Hidden fields and their errors
are rendered separately, and additional visible fields appear under Details.

The shared CSS uses the canonical tokens and existing controls. It adds section
surfaces and keeps actions in normal flow. The sections remain expanded. Adopt
this pattern only for ordinary standalone forms that need logical groups.
Keep transactional grids, identity flows, workflow configuration, attachment
workspaces and the separate Contract Create reference in their existing layouts.

## Record Detail Reuse Guide

Extend `record_detail_page.html` and populate `detail_heading` with the existing
`page_header.html`, then `detail_actions`, `detail_summary`, `detail_navigation`
and `detail_content` as needed. The base supplies the accepted shared application
context header and the opt-in Record Detail styles. Do not duplicate context
selectors. The visual reference is `docs/detail-page-reference.png`.

Inside a summary `dl.erp-record-summary`, include `record_summary_item.html` with
`heading`, `value`, optional `kind` (`date`, `datetime`, `number`, `amount`,
`identifier`, `status`), `label` for a status and optional `suffix`.
`record_detail_value.html` owns formatting only; calculate nothing in a template.

Use `.erp-record-section` with `form_section_header.html` and an explicitly
associated heading, followed by `.erp-record-section__body`. Ordinary information
can use `dl.erp-record-fields`; `.erp-record-wide` spans both desktop columns.
Use a labeled `.erp-record-nav` of real anchor links for populated sections.
Keep domain-specific forms and related tables intact, with existing permissions,
POST actions, CSRF and validation. Reuse existing DMS/evidence components.

`record_review_history.html` takes the actual `record` and ordered tenant-scoped
`record_history` revisions. Do not manufacture lifecycle events or expose raw
snapshots. Optional history needs an actual authorized source.
Verify each adopted route and meaningful state in Chrome at 1440/1024/390px;
the shared base alone does not establish verification or Product Owner acceptance.
