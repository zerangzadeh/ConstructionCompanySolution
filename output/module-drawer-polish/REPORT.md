# Module Drawer visual polish

MODULE DRAWER VISUAL POLISH: PASS
DRAWER HEIGHT: PASS
CARD DENSITY: PASS
MODULE ICON COLOR DIFFERENTIATION: PASS
ACTIVE MODULE CLARITY: PASS
RTL / RESPONSIVE: PASS
F1-F4 FOUNDATION PRESERVED: PASS
PRODUCT OWNER VISUAL ACCEPTANCE: PENDING

## Scope and grounding
Explicit bounded user request, existing uncommitted main at b97fcc45, tracking origin/main with no divergence. Existing unrelated modifications preserved. No commit or push. No new production authority or data/schema changes.

Product change: apps/accounts/static/css/erp_module_selector.css only. Compact padding/header/card spacing and typography, 4px secondary scroll indicator, stable restrained foreground/tint pairs keyed by existing module card identity. Active blue border/background/check, local icons and reduced-motion rules retained. Content-driven dimensions; no fixed/clipping drawer height.

Validation-only changes: tests/test_f3_module_selector.py and scripts/verification/f3_browser.mjs, adding 1024px, configurable evidence directory, geometry/color stability, touch swipe, copy fit and active color assertions. Existing isolated database runner reused.

Behavioral source hashes (baseline-hashes.json) verify unchanged selector template, icon template, JavaScript, and navigation adapter. Exact before/after links, active URLs, sidebar links and working-context values match for 15/15 scenarios. Authorized inventory unchanged: owner 11 families; restricted user 2 families. No Product Surface, permission, tenant, route or sidebar changes.

## Visual comparison
| Viewport | Before drawer | After drawer | Before card | After card | Indicator before/after |
|---|---:|---:|---:|---:|---:|
|1440|290.5px|211px|132px|104px|7px / 4px|
|1024|290.5px|211px|132px|104px|7px / 4px|
|390|265.5px|210px|132px|108px|7px / 4px|

Contracts captures manually reviewed at all three viewport widths, plus mobile Projects. Header/card hierarchy stays readable; icon tints differentiate identity while blue remains the active state. Close controls remain 44px high. Partial adjacent cards are intentional carousel previews; complete cards remain readable and reachable by scrolling. The lighter, thinner indicator is closer to cards. No gradients, card movement, remote dependencies or framework additions.

Before/after screenshots: before/*-open.png and after/*-open.png, with corresponding closed-page screenshots. Browser metrics: before/results.json and after/results.json. Icon contrast: icon-contrast.json, all icon/tint pairs exceed 3:1. User visual acceptance remains pending.

## Verification
Before: 15 real Chrome scenarios PASS.
After command: MODULE_SELECTOR_POLISH=1 MODULE_SELECTOR_EVIDENCE_DIRECTORY=output/module-drawer-polish/after .venv/Scripts/python.exe scripts/verification/module_selector_validate.py tests/test_f3_module_selector.py core/test_product_surface.py core/test_cep017_navigation.py -q --reuse-db --junitxml=output/module-drawer-polish/after-tests.xml
Result: 27 tests and 21 subtests PASS, including 15 real Chrome scenarios (1440/1024/390, owner and restricted accounts). Verified navigation from all visible owner cards, RTL carousel buttons and wheel scrolling, real mobile touch swipes, keyboard navigation, modal focus/restoration, Escape/backdrop/close, scroll lock, state preservation, reduced motion, stable module colors and no horizontal page overflow. External network requests blocked; local resources loaded successfully.
Ruff check/format, Django system check, JavaScript syntax and scoped git diff --check: PASS.
