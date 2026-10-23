# PD-WD-022 — Human decision, 2026-10-23

Authority: the Human's direct reply to the RV-022 / UIUX-F-048 question in this
chat. Status: **APPROVED OPTION 1**. This supersedes only the prior pending
PD-WD-022 disposition; historical audit evidence remains unchanged.

> Primary workflow-administration review view shall be business-labelled.
>
> Human-readable process, step and transition labels are the primary presentation.
>
> Technical identifiers, internal keys and implementation-level configuration remain available in a secondary disclosure / advanced configuration section for authorized administrators.
>
> Raw technical keys must not be used as the primary user-facing labels where an approved business label exists.
>
> This decision changes information priority only. It does not change workflow semantics, authorization, transition rules, stored identifiers or execution behavior.

Implementation boundary: existing stored business names and established Persian
outcome labels; a read-only step list and source/target transition table using the
existing UI patterns; technical identifiers/configuration retained in the existing
authorized version view's disclosure. No invented label semantics for unknown
codes, executable designer, domain mutation, grant, migration, Production or Git
write. Separate RV-016 and RV-021 blockers remain; this decision alone does not
open the Wave E gate.
