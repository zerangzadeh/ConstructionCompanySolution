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
