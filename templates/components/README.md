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
