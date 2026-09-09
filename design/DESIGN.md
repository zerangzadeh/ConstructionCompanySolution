---
name: Civil Slate Enterprise
colors:
  surface: '#f8f9ff'
  surface-dim: '#cbdbf5'
  surface-bright: '#f8f9ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#eff4ff'
  surface-container: '#e5eeff'
  surface-container-high: '#dce9ff'
  surface-container-highest: '#d3e4fe'
  on-surface: '#0b1c30'
  on-surface-variant: '#434655'
  inverse-surface: '#213145'
  inverse-on-surface: '#eaf1ff'
  outline: '#747686'
  outline-variant: '#c4c5d7'
  surface-tint: '#2151da'
  primary: '#0037b0'
  on-primary: '#ffffff'
  primary-container: '#1d4ed8'
  on-primary-container: '#cad3ff'
  inverse-primary: '#b7c4ff'
  secondary: '#565e74'
  on-secondary: '#ffffff'
  secondary-container: '#dae2fd'
  on-secondary-container: '#5c647a'
  tertiary: '#004f35'
  on-tertiary: '#ffffff'
  tertiary-container: '#006948'
  on-tertiary-container: '#76eab6'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#dce1ff'
  primary-fixed-dim: '#b7c4ff'
  on-primary-fixed: '#001551'
  on-primary-fixed-variant: '#0039b5'
  secondary-fixed: '#dae2fd'
  secondary-fixed-dim: '#bec6e0'
  on-secondary-fixed: '#131b2e'
  on-secondary-fixed-variant: '#3f465c'
  tertiary-fixed: '#85f8c4'
  tertiary-fixed-dim: '#68dba9'
  on-tertiary-fixed: '#002114'
  on-tertiary-fixed-variant: '#005137'
  background: '#f8f9ff'
  on-background: '#0b1c30'
  surface-variant: '#d3e4fe'
typography:
  headline-xl:
    fontFamily: Vazirmatn
    fontSize: 1.5rem
    fontWeight: '700'
    lineHeight: 2rem
    letterSpacing: -0.01em
  headline-lg:
    fontFamily: Vazirmatn
    fontSize: 1.5rem
    fontWeight: '700'
    lineHeight: 2.25rem
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Vazirmatn
    fontSize: 1.25rem
    fontWeight: '700'
    lineHeight: 1.875rem
  headline-sm:
    fontFamily: Vazirmatn
    fontSize: 1.125rem
    fontWeight: '600'
    lineHeight: 1.625rem
  body-lg:
    fontFamily: Vazirmatn
    fontSize: 1rem
    fontWeight: '400'
    lineHeight: 1.625rem
  body-md:
    fontFamily: Vazirmatn
    fontSize: 0.875rem
    fontWeight: '400'
    lineHeight: 1.5rem
  body-sm:
    fontFamily: Vazirmatn
    fontSize: 0.75rem
    fontWeight: '400'
    lineHeight: 1.25rem
  label-md:
    fontFamily: Vazirmatn
    fontSize: 0.875rem
    fontWeight: '600'
    lineHeight: 1.25rem
  label-sm:
    fontFamily: Vazirmatn
    fontSize: 0.75rem
    fontWeight: '600'
    lineHeight: 1rem
  code-md:
    fontFamily: JetBrains Mono
    fontSize: 0.875rem
    fontWeight: '500'
    lineHeight: 1.25rem
  code-sm:
    fontFamily: JetBrains Mono
    fontSize: 0.75rem
    fontWeight: '500'
    lineHeight: 1rem
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  space-2xs: 0.25rem
  space-xs: 0.5rem
  space-sm: 0.75rem
  space-md: 1rem
  space-lg: 1.5rem
  space-xl: 2rem
  space-2xl: 3rem
  sidebar-width-expanded: 16.25rem
  sidebar-width-collapsed: 4.5rem
  header-height: 3.75rem
  table-cell-padding-y: 0.625rem
  table-cell-padding-x: 1rem
---

## Source of Truth

These design documents define visual presentation only.

The existing ERP application remains authoritative for:
- models
- database schema
- URLs
- permissions
- validation
- tenant isolation
- workflows
- services
- business rules

When design documentation conflicts with existing application behavior,
preserve the existing application behavior.

---

## Brand & Style

This design system is engineered specifically for multi-tenant construction, civil engineering, and contracting enterprise resource planning (ERP). The operational environment demands high data density, absolute clarity, and zero ambiguity across complex multi-tier project structures, bill of quantities (BOQ), procurement schedules, and site compliance workflows.

The visual direction combines **Corporate Modernism** with architectural precision:
- **Structural Integrity:** Heavy reliance on clear spatial boundaries, structural hairline borders, and strict rhythmic alignment rather than ambient blurs or arbitrary decoration.
- **RTL-Native Priority:** Conceived from the ground up for Persian right-to-left layout dynamics, with balanced directional weight and symmetric logical flow.
- **Functional Contrast:** An authoritative dark slate navigation framework anchoring a clinical, high-visibility light workspace designed for prolonged daily usage under varied lighting conditions (from site offices to executive suites).
- **Technical Rigor:** Monospaced alphanumeric anchoring for project codes, fiscal figures, and National ID sequences interspersed naturally within fluid Persian typographic hierarchy.

## Colors

The color architecture enforces strict operational segregation between administrative hierarchy, interactive states, and mission-critical construction milestones.

### System Palette
- **Primary (`#1D4ED8`):** Deep Enterprise Blue. Serves as the primary operational action token (CTAs, interactive links, active pagination, and table row selections).
- **Secondary / Chrome (`#0F172A`):** Deep Slate Navy. Used exclusively for navigation shells, sidebars, and critical system headers. Paired with internal structural borders in `#1E293B`.
- **Canvas Base (`#F8FAFC`):** Light Slate. A low-strain, glare-reducing neutral canvas for dense data tables and card layouts.
- **Surface Layer (`#FFFFFF`):** Crisp pure white for cards, panels, modals, and input fields, enclosed by 1px subtle borders (`#E2E8F0`).

### Semantic Status Tokens
Construction schedules rely heavily on unambiguous status indicators:
- **Active / Completed (`#15803D` / Background `#F0FDF4` / Border `#BBF7D0`):** Forest Green for validated milestones, approved material receipts, and compliant inspections.
- **In-Progress (`#2563EB` / Background `#EFF6FF` / Border `#BFDBFE`):** Royal Blue for active crews, open work packages, and submittals under review.
- **Pending / Delayed (`#D97706` / Background `#FEF3C7` / Border `#FDE68A`):** Amber for schedule slippages, awaiting architect sign-off, or payment variance.
- **Blocked / Critical (`#DC2626` / Background `#FEF2F2` / Border `#FECACA`):** Crimson Red for safety violations, structural holds, stop-work orders, and cost overruns.
- **Draft / Archived (`#64748B` / Background `#F1F5F9` / Border `#CBD5E1`):** Neutral Slate for tentative requisitions, unposted journal entries, and archived tenders.

## Typography

Typography is calibrated for enterprise RTL reading performance. **Vazirmatn** serves as the primary Persian typeface, tuned with ample vertical leading to accommodate Persian ascenders and descenders without clipping in compact data grids.

### RTL & Numerical Rules
- **Bidirectional Isolation:** For alphanumeric codes (WBS codes, contract references, IBANs, inventory SKUs), enforce `dir="ltr"` and `unicode-bidi: isolate;` wrapped in `JetBrains Mono` or the tabular figures variant of Vazirmatn (`tnum`).
- **Financial & Quantity Data:** Metric units (e.g., m³, kg, tonnes) remain on the logical left of numeric figures in Persian syntax, while transaction amounts leverage monospaced digit columns for vertical scanning alignment across data tables.
- **Weight Strategy:** Restrict body text to `400` (Regular) and operational headers to `600` (SemiBold) and `700` (Bold). Avoid ultra-thin or hairline weights that degrade on low-contrast industrial monitors.

## Layout & Spacing

The layout is grounded in a compact, industrial 4px base increment (`0.25rem`), optimized for enterprise screens where high vertical throughput reduces scroll fatigue.

### Layout Scaffold
- **Master Root Container:** HTML root sets `dir="rtl"` and `lang="fa-IR"`.
- **Sidebar (Logical Start):** Fixed on the visual right side of the screen. Standard width is `16.25rem` (260px), collapsible to `4.5rem` (72px).
- **Workspace Canvas:** Fluid grid scaling from `100%` width up to a maximum inner container max-width of `1600px` for ultra-wide desktop monitors, preventing field inputs from over-stretching.
- **Data Densities:**
  - *Standard:* Form fields at 40px height, table rows at 48px height.
  - *Compact:* Form fields at 32px height, table rows at 36px height for extensive bill-of-quantities (BOQ) entry screens.

### Responsive Breakpoints
- **Mobile (`< 768px`):** Off-canvas sidebar, single-column forms and cards. Complex ERP data tables must remain tabular and use horizontal scrolling inside their own container. Only simple non-tabular lists may stack into cards.
- **Tablet (`768px - 1024px`):** Mini-sidebar (collapsed mode with hover tooltips), 2-column KPI card grids.
- **Desktop (`> 1024px`):** Persistent full sidebar, 4-column KPI cards, multi-pane split view for item inspections and audit logs.

## Elevation & Depth

To maintain high performance in server-rendered templates (Django/HTMX) and ensure visual precision, the system prioritizes **structural borders and tonal elevation** over soft blur shadows.

- **Level 0 (Canvas):** `#F8FAFC` flat surface.
- **Level 1 (Cards, Modules, Sidebars):** `#FFFFFF` surface enclosed by a crisp `1px solid #E2E8F0` border. No drop shadow is applied in default state.
- **Level 2 (Hovered Cards, Dropdowns, Action Popovers):** `#FFFFFF` surface with `box-shadow: 0 4px 6px -1px rgba(15, 23, 42, 0.08), 0 2px 4px -2px rgba(15, 23, 42, 0.04);` and `border: 1px solid #CBD5E1;`.
- **Level 3 (Modals, Overlays, Slide-in Panels):** `#FFFFFF` surface with `box-shadow: 0 20px 25px -5px rgba(15, 23, 42, 0.12), 0 8px 10px -6px rgba(15, 23, 42, 0.08);` with a fixed backdrop tint of `rgba(15, 23, 42, 0.60)` with backdrop blur disabled for instantaneous render response.

## Shapes

The geometric aesthetic is disciplined and architectural, reflecting structural engineering blueprints.

- **Controls & Buttons:** Strictly `8px` (`rounded-lg` in standard Tailwind configuration or custom `--radius-control: 8px`). This provides distinct tactile presence without soft consumer-grade roundness.
- **Cards, Panels & Containers:** Sized at `10px` to `12px` (`--radius-card: 10px`). Structural modules feel cohesive and unified when arranged in grids.
- **Status Badges & Chips:** `6px` for small chips, or fully circular pills (`rounded-full`) exclusively for numeric count indicators.
- **Inputs & Select Menus:** Strict `8px` corner radius matching button standards for seamless form row alignment.

## Components

### Buttons
- **Primary:** Background `#1D4ED8`, text `#FFFFFF`, border `transparent`. Hover: `#1E40AF`. Active: `#1E3A8A`. Focus ring: `2px solid #93C5FD` with `2px` offset. Radius: `8px`. Height: `38px` (compact: `32px`).
- **Secondary / Outline:** Background `#FFFFFF`, text `#0F172A`, border `1px solid #CBD5E1`. Hover: `#F1F5F9`. Radius: `8px`.
- **Destructive:** Background `#DC2626`, text `#FFFFFF`. Hover: `#B91C1C`. Radius: `8px`.
- **Sidebar Nav Item:** Background `transparent`, text `#94A3B8`. Hover: Background `#1E293B`, text `#F8FAFC`. Active: Background `#1D4ED8`, text `#FFFFFF`. Icon logical margin-left: `0.75rem`.

### Form Fields & Inputs
- **Base Input:** Background `#FFFFFF`, border `1px solid #CBD5E1`, border-radius `8px`, text `#0F172A`, placeholder `#94A3B8`. Padding: `0.5rem 0.75rem`. Focus: Border `#1D4ED8`, ring `1px solid #1D4ED8`.
- **Validation State (Error):** Border `#DC2626`, ring `1px solid #DC2626`, error message in `#DC2626` font size `0.75rem` with logical right-aligned warning icon.
- **Code Inputs (WBS/Contract):** Standard input styled with `JetBrains Mono`, `dir="ltr"`, text-align logical right for easy Persian context integration.

### Cards & Metrics (KPI Widgets)
- **Container:** Pure white background, `10px` border-radius, `1px solid #E2E8F0` border, padding `1.25rem`.
- **Structure:** 
  - Top: Logical right shows label in `#64748B` (`text-sm`), logical left holds semantic status chip or icon badge.
  - Middle: Primary metric in `#0F172A` (`text-2xl font-bold font-mono-numeric`).
  - Bottom: Trend or contextual footer separated by optional subtle border `#F1F5F9`.

### Data Tables (Construction BOQ & Schedules)
- **Header:** Background `#F8FAFC`, text `#475569` (`text-xs font-semibold`), border bottom `1px solid #CBD5E1`. Padding `0.625rem 1rem`. Logical text alignment matches content.
- **Row:** Background `#FFFFFF`, border bottom `1px solid #F1F5F9`. Hover: `#F8FAFC`.
- **Selected Row:** Background `#EFF6FF`, border bottom `1px solid #BFDBFE`.
- **Numeric Cells:** Class `tabular-nums font-mono text-left` to support fast mental comparison of quantities and estimates across rows.

### Chips & Badges
- **Status Chip:** Height `24px`, padding `0 8px`, border-radius `6px`, font size `0.75rem`, font weight `500`.
  - *Active:* Text `#15803D`, background `#DCFCE7`, border `1px solid #BBF7D0`.
  - *Delayed:* Text `#B45309`, background `#FEF3C7`, border `1px solid #FDE68A`.
  - *Blocked:* Text `#B91C1C`, background `#FEE2E2`, border `1px solid #FECACA`.
  - *In-Progress:* Text `#1D4ED8`, background `#DBEAFE`, border `1px solid #BFDBFE`.

### HTMX Dynamic Indicators
- Dynamic swapped elements trigger instant class transition via `htmx-request` targeting an inline loader: a subtle 2px royal blue top-progress bar (`#1D4ED8`) anchored along the top edge of the active panel, avoiding jarring full-screen spinners.