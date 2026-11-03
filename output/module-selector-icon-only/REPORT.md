# Icon-only module trigger and bottom close

Explicit requested presentation update on main at 28a98960. No commits or pushes; unrelated edits preserved.

- Trigger text removed, accessible name retained; four connected puzzle pieces now have distinct blue, violet, green and amber fills. Trigger SVG 24px in a compact 40px desktop / 44px mobile button.
- Text close moved from heading to a 44px icon-only button at the bottom-left edge; aria-label/title, existing close handler, Escape and backdrop retained.
- Bottom button uses the existing carousel edge gutter, without added footer height. Hidden arrows retain their gutter to avoid overlap with short module lists. Focus trapping excludes invisible arrow controls.
- Module definitions, active detection, URLs, filtering, authorization, tenant/project/site context and sidebar unchanged.

Validation: 5 presentation tests + 5 subtests PASS; Django check PASS; scoped whitespace and JavaScript syntax checks PASS. 15 real Chrome scenarios PASS across 1440/1024/390 with owner and restricted accounts, including icon-only trigger, four fill colors, bottom close position and 44px target, no visible-card overlap, drawer <=211px, modal keyboard/Escape/backdrop/focus, RTL controls, mobile swipe, preserved context and all owner card destinations. Screenshots and metrics: browser/results.json and browser/*-open.png / *-closed.png. JUnit: tests.xml.
