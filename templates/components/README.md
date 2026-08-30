# Template component conventions

Shared Django template fragments belong in this directory when they represent a
stable, reusable UI pattern. Components must receive all required context
explicitly through `{% include ... with ... only %}` so that their dependencies
remain clear and they do not accidentally rely on tenant or request state.

- `form_errors.html` renders non-field validation errors for one bound form.
- `form_field.html` renders one labelled Django form field and its errors.
- `messages.html` renders Django's framework messages from the shared context
  processor.

Keep business decisions, authorization checks, and formatting of financial
values outside components. Components are presentation-only and must preserve
server-side validation as the source of truth.
