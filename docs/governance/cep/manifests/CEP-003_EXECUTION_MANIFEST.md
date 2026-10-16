# CEP-003 Execution Manifest

## Authorization and repository grounding — 2026-10-15

- Authorization: `AUTH-BATCH-002`, Development / non-production only.
- Execution order: first serial package only; no later CEP was started.
- Branch: `cep/CEP-003-localization-accessibility`.
- Baseline HEAD: `17dff5f48eb34b6de3a22e0597861b0581146f33` (`main`).
- Baseline working tree, name-status, and diff stat: clean / empty / empty.
- Canonical prompt: `CEP-003_EXECUTION_PROMPT.md`, SHA-256
  `17589d700d9ae3b4d17f2adca362439dda3ea3eda32e8ab1b5771937954b7048`.

## Grounding result

- `core.forms.JalaliDateMixin`, `core.jalali`, and the shared formatting filters
  already provide the Jalali input/display and IRR/numeric presentation contract.
- The shared `components/form_field.html` did not programmatically associate a
  rendered control with its help or validation text.
- Login already has landmarks and its own error associations. The shared
  primitive now gives the same association to component-based forms.
- User-visible product naming was inconsistent (`سازه‌یار` / `سازه یار` versus
  `بنیرا`) in 28 templates and Django Admin labels.
- No user-entered reversal-date field exists in the approved reversal surfaces;
  no date semantics, form fields, endpoint, or authorization behavior was added.

## Actual execution touch set

| Surface | Bounded change | Migration impact |
| --- | --- | --- |
| `core/templatetags/form_accessibility.py` | Shared safe widget rendering with stable help/error associations and invalid-state semantics. | None |
| `templates/components/form_field.html` | Emits stable help/error IDs and uses the shared accessible renderer. | None |
| `config/settings/base.py` | Registers the shared template-tag library because `core` is not an installed Django app. | None |
| `core/test_cep003_localization_accessibility.py` | Focused Jalali, RTL, landmark, accessibility, and naming regression evidence. | None |
| Presentation templates and `config/urls.py` | Presentation-only BONIRA naming cleanup. | None |

No models, migrations, stored dates, date/time semantics, money values,
authorization behavior, tenant scope, routes, workflow behavior, or production
configuration changed.
