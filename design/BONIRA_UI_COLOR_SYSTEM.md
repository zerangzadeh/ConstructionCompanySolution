# BONIRA UI Color System
**Status:** Canonical / Approved  
**Scope:** All BONIRA product UI, Django Templates, Tailwind CSS, reusable components, authentication pages, application shell, admin/platform UI, reports, and operational workbenches.

> **Source of Truth:** This file defines the approved BONIRA UI color tokens.  
> Codex must use these tokens instead of introducing new hard-coded colors.

---

## 1. Core Brand Palette

| Token | Hex | Primary use |
|---|---|---|
| `brand.deep-navy` | `#0E2746` | Sidebar, dark navigation surfaces, strong brand text |
| `brand.royal-blue` | `#1563D6` | Primary actions, links, focus, active state |
| `brand.amber-orange` | `#F59E0B` | Controlled brand accent, attention |
| `brand.warm-amber` | `#FFC451` | Secondary warm accent, highlights |
| `brand.light-gray` | `#E5ECF4` | Soft borders, separators, subtle neutral surfaces |
| `brand.white` | `#FFFFFF` | Main surfaces, cards, forms |

---

## 2. Neutral Palette

| Token | Hex | UI role |
|---|---|---|
| `neutral.ink` | `#0F172A` | Primary text |
| `neutral.slate` | `#475569` | Secondary text |
| `neutral.muted` | `#64748B` | Tertiary text, metadata, icons |
| `neutral.soft` | `#F7F9FC` | Soft background, hover surface, grouped sections |
| `neutral.border` | `#CBD5E1` | Stronger input/control border |

### Neutral hierarchy
- Primary text → `neutral.ink`
- Secondary text → `neutral.slate`
- Supporting / tertiary text → `neutral.muted`
- Default page/card surface → `brand.white`
- Soft surface → `neutral.soft`
- Soft separator → `brand.light-gray`
- Control/input border → `neutral.border`

---

## 3. Semantic Palette

| Token | Hex | Meaning |
|---|---|---|
| `semantic.success` | `#15803D` | Success / completed / healthy |
| `semantic.warning` | `#D97706` | Warning / caution / pending attention |
| `semantic.danger` | `#B91C1C` | Error / destructive / critical |

### Semantic rules
- Do not use semantic colors decoratively.
- `success` is only for positive status or successful completion.
- `warning` is only for caution, attention, or risk.
- `danger` is only for errors, destructive actions, failed states, or critical alerts.

---

## 4. Canonical CSS Tokens

Use these variables globally.  
Do not duplicate literal color values inside component CSS unless required by an external library.

```css
:root {
  /* Brand */
  --bonira-deep-navy: #0E2746;
  --bonira-royal-blue: #1563D6;
  --bonira-amber-orange: #F59E0B;
  --bonira-warm-amber: #FFC451;
  --bonira-light-gray: #E5ECF4;
  --bonira-white: #FFFFFF;

  /* Neutrals */
  --bonira-ink: #0F172A;
  --bonira-slate: #475569;
  --bonira-muted: #64748B;
  --bonira-soft: #F7F9FC;
  --bonira-border: #CBD5E1;

  /* Semantic */
  --bonira-success: #15803D;
  --bonira-warning: #D97706;
  --bonira-danger: #B91C1C;

  /* Semantic UI aliases */
  --color-bg-page: var(--bonira-white);
  --color-bg-surface: var(--bonira-white);
  --color-bg-subtle: var(--bonira-soft);

  --color-text-primary: var(--bonira-ink);
  --color-text-secondary: var(--bonira-slate);
  --color-text-muted: var(--bonira-muted);

  --color-border-subtle: var(--bonira-light-gray);
  --color-border-control: var(--bonira-border);

  --color-primary: var(--bonira-royal-blue);
  --color-primary-strong: var(--bonira-deep-navy);

  --color-accent: var(--bonira-amber-orange);
  --color-accent-soft: var(--bonira-warm-amber);

  --color-success: var(--bonira-success);
  --color-warning: var(--bonira-warning);
  --color-danger: var(--bonira-danger);

  /* Alpha variants are allowed only from approved base colors */
  --color-focus-ring: rgb(21 99 214 / 13%);
  --color-primary-hover-overlay: rgb(21 99 214 / 8%);
  --color-danger-soft: rgb(185 28 28 / 6%);
  --color-success-soft: rgb(21 128 61 / 7%);
  --color-warning-soft: rgb(217 119 6 / 8%);
}
```

---

## 5. Tailwind Mapping

For Tailwind, map the approved tokens once and use semantic class names.

```js
// tailwind.config.js
module.exports = {
  theme: {
    extend: {
      colors: {
        bonira: {
          navy: "#0E2746",
          blue: "#1563D6",
          amber: "#F59E0B",
          "amber-soft": "#FFC451",
          gray: "#E5ECF4",
          white: "#FFFFFF",

          ink: "#0F172A",
          slate: "#475569",
          muted: "#64748B",
          soft: "#F7F9FC",
          border: "#CBD5E1",

          success: "#15803D",
          warning: "#D97706",
          danger: "#B91C1C",
        },
      },
    },
  },
};
```

Preferred examples:

```html
<button class="bg-bonira-blue text-white hover:bg-bonira-navy">
  ثبت
</button>

<div class="bg-bonira-soft border border-bonira-gray">
  ...
</div>

<p class="text-bonira-ink">متن اصلی</p>
<p class="text-bonira-slate">متن ثانویه</p>
<p class="text-bonira-muted">متن کم‌اهمیت</p>
```

---

## 6. Component Color Rules

### Primary button
- Background: `brand.royal-blue`
- Text: `brand.white`
- Hover: `brand.deep-navy`
- Focus ring: alpha variant of `brand.royal-blue`
- Do not use amber as the default primary action color.

### Secondary button
- Background: `brand.white`
- Text: `brand.deep-navy` or `neutral.ink`
- Border: `neutral.border`
- Hover surface: `neutral.soft`

### Destructive button
- Background or text: `semantic.danger`
- Use only for destructive actions.

### Inputs
- Surface: `brand.white`
- Text: `neutral.ink`
- Label: `neutral.ink`
- Placeholder/help: `neutral.muted`
- Default border: `neutral.border`
- Focus border: `brand.royal-blue`
- Error border/text: `semantic.danger`

### Sidebar
- Main background: `brand.deep-navy`
- Primary foreground: `brand.white`
- Active indicator: `brand.royal-blue`
- Amber may be used only as a restrained accent, not for large navigation surfaces.

### Header / Topbar
- Prefer `brand.white` or `neutral.soft`.
- Use `neutral.ink` for primary content.
- Use `brand.royal-blue` for active links/actions.

### Cards / Panels
- Surface: `brand.white`
- Secondary surface: `neutral.soft`
- Border: `brand.light-gray`
- Avoid tinted decorative card backgrounds unless the color carries semantic meaning.

### Status
- Success → `semantic.success`
- Warning → `semantic.warning`
- Error/Critical → `semantic.danger`
- Neutral/Informational → `brand.royal-blue` or neutral tokens depending context

---

## 7. Usage Hierarchy

Use colors in this order of importance:

1. **White / Soft neutral** — dominant application surfaces
2. **Deep Navy** — structural/navigation authority
3. **Royal Blue** — interaction and active state
4. **Ink / Slate / Muted** — text hierarchy
5. **Amber** — restrained brand accent
6. **Semantic colors** — status only

BONIRA should not look colorful.  
The overall product should remain **calm, enterprise, precise, and restrained**.

---

## 8. Prohibited Practices

Codex must NOT:

- introduce arbitrary hex colors;
- create near-duplicate grays or blues;
- use Tailwind default colors such as `slate-*`, `blue-*`, `gray-*`, `red-*`, etc. when an approved BONIRA token exists;
- use gradients as decorative UI styling;
- use amber as the dominant CTA color;
- use semantic red/green/orange for decoration;
- hard-code colors repeatedly in templates;
- create module-specific color palettes;
- change logo colors outside official logo assets;
- use opacity to make text fail WCAG 2.2 AA contrast.

If a new color is genuinely required, it must be proposed as a Design System change instead of being silently added.

---

## 9. Alpha / Transparency Rule

Alpha variants are allowed only from approved palette colors.

Allowed example:

```css
background: rgb(21 99 214 / 8%);
box-shadow: 0 0 0 4px rgb(21 99 214 / 13%);
```

Not allowed:

```css
background: #EAF2FF; /* new unapproved blue */
```

Prefer deriving subtle states through alpha from an approved base color.

---

## 10. Accessibility

- Target WCAG 2.2 AA.
- Body text must have sufficient contrast against its background.
- Never rely on color alone to communicate status.
- Error/success/warning states must include text, icon, or another non-color cue.
- Focus must remain clearly visible.
- Disabled states must remain legible.

---

## 11. Implementation Rules for Codex

When modifying BONIRA UI:

1. Treat this file as the canonical color authority.
2. Reuse existing CSS variables / Tailwind tokens.
3. Replace hard-coded legacy colors with the nearest approved semantic token.
4. Do not alter business logic, permissions, routing, forms, or workflows merely for visual alignment.
5. Preserve Persian-first RTL behavior.
6. Preserve LTR direction for technical identifiers, currency strings, codes, and values when required.
7. Use the official BONIRA SVG assets without recoloring or tracing them.
8. Run a repository search for newly introduced hex colors before completion.
9. Report any color that cannot be mapped safely instead of inventing a replacement.
10. New UI components must conform to this token system from creation.

---

## 12. Approved Hex Registry

These are the only canonical hexadecimal colors currently approved for BONIRA UI:

```text
#0E2746  Deep Navy
#1563D6  Royal Blue
#F59E0B  Amber Orange
#FFC451  Warm Amber
#E5ECF4  Light Gray
#FFFFFF  White

#0F172A  Ink
#475569  Slate
#64748B  Muted
#F7F9FC  Soft Surface
#CBD5E1  Border

#15803D  Success
#D97706  Warning
#B91C1C  Danger
```

---

## 13. Design-System Principle

**Use semantic tokens, not visual guesses.**

Bad:

```css
color: #132238;
border-color: #CCD7E4;
background: #F8FAFD;
```

Good:

```css
color: var(--color-text-primary);
border-color: var(--color-border-control);
background: var(--color-bg-subtle);
```

This ensures BONIRA Login, Application Shell, operational forms, dashboards, tables, dialogs, reports, and future modules remain visually consistent.
