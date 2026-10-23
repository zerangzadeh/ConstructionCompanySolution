# BONIRA UI/UX Root Pattern Catalogue

## Document status

- Status: `STATIC_TAXONOMY_STABLE`
- Repository baseline: `main @ 43ac319c6e73e48ca9626461b73987922c498ec3`
- Canonical human-readable path: `docs/governance/uiux/UIUX_ROOT_PATTERN_CATALOGUE.md`
- Machine-readable companion: `UIUX_ROOT_PATTERN_CATALOGUE.yaml`

This catalogue groups evidence-backed UI/UX findings into systemic patterns. A root pattern does not authorize remediation or any business/domain change.

## RP-C01-TECHNICAL-LANGUAGE-LEAK — نشت زبان فنی و حاکمیتی به رابط کاربر

**Status:** `CONFIRMED_SYSTEMIC`  
**Remediation class:** `SHARED_TERMINOLOGY_AND_COPY_STANDARD`  
**Domain change expected:** `False`  
**Evidence-backed findings:** 52  
**Observed modules:** Accounting, Billing, Billing / Statutory, Compliance, Contracts, Core, Documents, Equipment, Estimates, Fixed Assets, Inventory, Knowledge, Materials, Organizations, Parties, Partner Qualification, Payroll, Payroll / ESS, Procurement, Procurement Supplier Portal, Projects, Reporting, Shared Forms, Shared Shell, Subledgers, Support, Timekeeping, Treasury, Workflow Administration, Workforce, Workforce / ESS

Internal governance, authorization, implementation, evidence, source, boundary or architecture vocabulary is shown as primary operational language.

Representative finding IDs: UIUX-F-001, UIUX-F-003, UIUX-F-004, UIUX-F-005, UIUX-F-007, UIUX-F-009, UIUX-F-010, UIUX-F-011, UIUX-F-014, UIUX-F-015, UIUX-F-019, UIUX-F-020 …

## RP-C02-MODEL-REPRESENTATION-EXPOSED — نمایش نمایشگرهای فنی مدل به کاربر

**Status:** `CONFIRMED_SYSTEMIC`  
**Remediation class:** `PRESENTATION_ADAPTER_AND_SELECTORS`  
**Domain change expected:** `False`  
**Evidence-backed findings:** 30  
**Observed modules:** Accounting, Audit, Billing, Commercial, Compliance, Daily Reports, Equipment, Inventory, Knowledge, Payroll / ESS, Reporting, Subledgers, Support, Timekeeping, Treasury, Workflow Administration, Workforce, Workforce / ESS

Encoded values, raw status/source values, UUID-like identifiers or internal event references are presented to users instead of business-identifying representations.

Representative finding IDs: UIUX-F-002, UIUX-F-012, UIUX-F-021, UIUX-F-024, UIUX-F-030, UIUX-F-036, UIUX-F-037, UIUX-F-039, UIUX-F-041, UIUX-F-042, UIUX-F-045, UIUX-F-046 …

## RP-C03-EXCESSIVE-TECHNICAL-INPUT — ورودی فنی قابل اجتناب

**Status:** `CONFIRMED_CROSS_MODULE`  
**Remediation class:** `FORM_SIMPLIFICATION_AND_DERIVATION`  
**Domain change expected:** `False`  
**Evidence-backed findings:** 13  
**Observed modules:** Accounting, Billing / Statutory, Commercial, Daily Reports, Equipment, Knowledge, Payroll, Procurement Supplier Portal, Reporting, Subledgers, Timekeeping, Workforce

Users are asked to manually enter values the UI could derive, select, or encode.

Representative finding IDs: UIUX-F-002, UIUX-F-012, UIUX-F-046, UIUX-F-056, UIUX-F-059, UIUX-F-060, UIUX-F-061, UIUX-F-070, UIUX-F-071, UIUX-F-075, UIUX-F-078, UIUX-F-079 …

## RP-C04-WEAK-ACTION-HIERARCHY — سلسله‌مراتب ضعیف اقدامات

**Status:** `CONFIRMED_SYSTEMIC`  
**Remediation class:** `TASK_FIRST_ACTION_HIERARCHY`  
**Domain change expected:** `False`  
**Evidence-backed findings:** 8  
**Observed modules:** Compliance, Equipment, Fixed Assets, Payroll, Procurement, Subledgers, Timekeeping, Workforce / ESS

Many legitimate actions are rendered with equal weight instead of identifying the primary task or current next action.

Representative finding IDs: UIUX-F-006, UIUX-F-008, UIUX-F-013, UIUX-F-022, UIUX-F-025, UIUX-F-028, UIUX-F-035, UIUX-F-040

## RP-C05-TASK-GUIDANCE-DEFICIT — کمبود راهنمای وظیفه‌محور

**Status:** `CONFIRMED_SYSTEMIC`  
**Remediation class:** `TASK_COPY_AND_CONTEXTUAL_HELP`  
**Domain change expected:** `False`  
**Evidence-backed findings:** 14  
**Observed modules:** Core, Estimates, Inventory, Organizations, Partner Qualification, Payroll, Procurement, Projects, Reporting, Shared Shell, Subledgers, Timekeeping, Treasury

Pages explain controls, boundaries or implementation status more readily than the user's objective, prerequisites, and next step.

Representative finding IDs: UIUX-F-001, UIUX-F-004, UIUX-F-005, UIUX-F-009, UIUX-F-014, UIUX-F-015, UIUX-F-019, UIUX-F-020, UIUX-F-023, UIUX-F-032, UIUX-F-033, UIUX-F-041 …

## RP-C06-GENERIC-FORM-ACTION — اقدام عمومی در فرم‌های متفاوت

**Status:** `CONFIRMED_SYSTEMIC`  
**Remediation class:** `TASK_SPECIFIC_CTA_LABELS`  
**Domain change expected:** `False`  
**Evidence-backed findings:** 3  
**Observed modules:** Billing, Shared Forms, Timekeeping

A shared form template uses a generic governance-oriented primary button instead of a task-specific action label.

Representative finding IDs: UIUX-F-003, UIUX-F-082, UIUX-F-101

## RP-C07-WORKFLOW-NOT-JOURNEY-ORIENTED — نمایش گردش‌کار به شکل فرمان‌ها به جای سفر کاربر

**Status:** `CONFIRMED_SYSTEMIC`  
**Remediation class:** `STATE_AWARE_JOURNEY_PRESENTATION`  
**Domain change expected:** `False`  
**Evidence-backed findings:** 9  
**Observed modules:** Compliance, Equipment, Fixed Assets, Payroll, Procurement, Subledgers, Timekeeping

Domain commands/states are surfaced directly without a user-facing progression, stage model, or recommended next step.

Representative finding IDs: UIUX-F-006, UIUX-F-008, UIUX-F-013, UIUX-F-025, UIUX-F-027, UIUX-F-028, UIUX-F-040, UIUX-F-062, UIUX-F-068

## RP-C08-WEAK-EMPTY-STATE — وضعیت خالی کم‌راهنما

**Status:** `CONFIRMED_CROSS_MODULE`  
**Remediation class:** `STATE_AWARE_EMPTY_STATES`  
**Domain change expected:** `False`  
**Evidence-backed findings:** 4  
**Observed modules:** Core, Payroll, Payroll / ESS, Workforce / ESS

Empty states emphasize access/source state or absence without clearly distinguishing why nothing is shown and what the user can do next.

Representative finding IDs: UIUX-F-007, UIUX-F-015, UIUX-F-021, UIUX-F-042

## RP-C09-INCONSISTENT-DETAIL-AFFORDANCE — ناهماهنگی روش ورود به جزئیات

**Status:** `CONFIRMED_SYSTEMIC`  
**Remediation class:** `CANONICAL_LIST_DETAIL_PATTERN`  
**Domain change expected:** `False`  
**Evidence-backed findings:** 1  
**Observed modules:** Shared List Pattern

Lists use inconsistent record-opening patterns: whole row, name link, multiple linked cells, explicit button, or icon-only action.

Representative finding IDs: UIUX-F-018

## RP-C10-NAVIGATION-STATE-INCONSISTENCY — ناهماهنگی وضعیت در ناوبری

**Status:** `CONFIRMED_SHARED_COMPONENT`  
**Remediation class:** `NAVIGATION_STATE_NORMALIZATION`  
**Domain change expected:** `False`  
**Evidence-backed findings:** 2  
**Observed modules:** Shared Navigation

The shared navigation can duplicate the same destination in enabled and disabled states or use duplicated navigation identifiers.

Representative finding IDs: UIUX-F-016, UIUX-F-017

## RP-C11-INFORMATION-ARCHITECTURE-MISMATCH — عدم انطباق معماری اطلاعات با قابلیت واقعی

**Status:** `CONFIRMED_CROSS_SURFACE`  
**Remediation class:** `INFORMATION_ARCHITECTURE_HARMONIZATION`  
**Domain change expected:** `False`  
**Evidence-backed findings:** 6  
**Observed modules:** Partner Qualification, Shared Navigation, Support, Timekeeping, Workforce, Workforce / ESS

Navigation/grouping does not consistently match reachable capabilities or user intents.

Representative finding IDs: UIUX-F-017, UIUX-F-022, UIUX-F-037, UIUX-F-040, UIUX-F-106, UIUX-F-108

## RP-C12-POST_RENDER_LOCALIZATION — بومی‌سازی پس از رندر

**Status:** `CONFIRMED_SHARED_IMPLEMENTATION_PATTERN`  
**Remediation class:** `AUTHORITATIVE_SERVER_SIDE_LOCALIZATION`  
**Domain change expected:** `False`  
**Evidence-backed findings:** 3  
**Observed modules:** Billing, Knowledge, Shared Localization

Shared JavaScript rewrites exact English text nodes after render instead of relying solely on canonical localized presentation labels.

Representative finding IDs: UIUX-F-029, UIUX-F-036, UIUX-F-072

## RP-C13-OPERATIONAL-AUDIT-CONFLATION — ادغام نمای عملیاتی و نمای ممیزی/ردیابی

**Status:** `CONFIRMED_SYSTEMIC`  
**Remediation class:** `PROGRESSIVE_DISCLOSURE_AUDIT_LAYER`  
**Domain change expected:** `False`  
**Evidence-backed findings:** 23  
**Observed modules:** Accounting, Billing, Compliance, Contracts, Equipment, Knowledge, Materials, Payroll, Reporting, Support, Treasury, Workforce

Operational pages place lineage, evidence hashes, source versions, control guarantees or audit metadata beside normal task data instead of progressively disclosing them.

Representative finding IDs: UIUX-F-030, UIUX-F-031, UIUX-F-032, UIUX-F-033, UIUX-F-038, UIUX-F-039, UIUX-F-043, UIUX-F-045, UIUX-F-051, UIUX-F-052, UIUX-F-062, UIUX-F-064 …

## RP-C14-SEMANTIC-LANDMARK-INCONSISTENCY — ناهماهنگی Landmark معنایی

**Status:** `CONFIRMED_LOCAL_PATTERN`  
**Remediation class:** `SEMANTIC_HTML_NORMALIZATION`  
**Domain change expected:** `False`  
**Evidence-backed findings:** 5  
**Observed modules:** Accounts, Reporting, Workforce

A page template introduces a main landmark inside the global main landmark.

Representative finding IDs: UIUX-F-034, UIUX-F-044, UIUX-F-047, UIUX-F-049, UIUX-F-107

## RP-C15-SHARED-FORM-PATTERN-BYPASS — دور زدن الگوی مشترک فرم

**Status:** `CONFIRMED_CROSS_SURFACE`  
**Remediation class:** `SHARED_FORM_COMPONENT_ADOPTION`  
**Domain change expected:** `False`  
**Evidence-backed findings:** 5  
**Observed modules:** Billing, Knowledge, Support

Some forms use raw HTML inputs/buttons instead of the shared accessible form components, causing labeling, validation and interaction inconsistency.

Representative finding IDs: UIUX-F-037, UIUX-F-063, UIUX-F-089, UIUX-F-099, UIUX-F-101

## RP-C16-DEVELOPMENT-ARTEFACT-LEAK — نشت شناسه‌های توسعه و Roadmap به محصول

**Status:** `CONFIRMED_SYSTEMIC`  
**Remediation class:** `REMOVE_DELIVERY_METADATA_FROM_RUNTIME_UI`  
**Domain change expected:** `False`  
**Evidence-backed findings:** 3  
**Observed modules:** Contracts, Equipment, Reporting

Delivery-stage, CEP, phase or roadmap identifiers appear visibly on operational/product pages.

Representative finding IDs: UIUX-F-038, UIUX-F-043, UIUX-F-096

## RP-C17-CONFIGURATION-NOT-VISUALIZED — نمایش تنظیمات پیچیده به شکل داده فنی به جای مدل بصری

**Status:** `CONFIRMED_LOCAL_PATTERN`  
**Remediation class:** `VISUAL_CONFIGURATION_PRESENTATION`  
**Domain change expected:** `False`  
**Evidence-backed findings:** 3  
**Observed modules:** Compliance, Workflow Administration, Workforce

Complex configurable process structures are presented mainly as raw keys, types, transitions or configuration text rather than a visual/business representation.

Representative finding IDs: UIUX-F-048, UIUX-F-071, UIUX-F-095

## RP-C18-CASCADE-FILTERING-INCONSISTENT — عدم یکنواختی فیلتر آبشاری انتخاب‌ها

**Status:** `CONFIRMED_SYSTEMIC`  
**Remediation class:** `CONTEXT_AWARE_CASCADE_FILTERING`  
**Domain change expected:** `False`  
**Evidence-backed findings:** 13  
**Observed modules:** Accounting, Billing, Compliance, Daily Reports, Equipment, Payroll, Procurement, Support, Treasury

Dependent selections such as Project→Site→Phase or Project→Request are sometimes narrowed only after submit, or not narrowed at all, even though the system already knows the relationship.

Representative finding IDs: UIUX-F-054, UIUX-F-055, UIUX-F-057, UIUX-F-058, UIUX-F-074, UIUX-F-076, UIUX-F-077, UIUX-F-078, UIUX-F-081, UIUX-F-084, UIUX-F-086, UIUX-F-087 …

## RP-C19-DERIVABLE-DATA-REENTRY — ورود مجدد داده قابل استخراج

**Status:** `CONFIRMED_SYSTEMIC`  
**Remediation class:** `FORM_INTELLIGENCE_AND_DATA_REUSE`  
**Domain change expected:** `False`  
**Evidence-backed findings:** 12  
**Observed modules:** Accounting, Billing / Statutory, Commercial, Daily Reports, Equipment, Knowledge, Payroll, Procurement, Procurement Supplier Portal, Treasury

Users are asked to enter values, metadata, identifiers or companion fields that can be derived from an existing selection, current context, uploaded content or system-generated identity.

Representative finding IDs: UIUX-F-054, UIUX-F-056, UIUX-F-059, UIUX-F-060, UIUX-F-061, UIUX-F-070, UIUX-F-075, UIUX-F-076, UIUX-F-078, UIUX-F-079, UIUX-F-080, UIUX-F-088

## RP-C20-HOME-LINK-DIRECTORY — صفحه اصلی به‌عنوان فهرست لینک به جای داشبورد وظیفه‌محور

**Status:** `CONFIRMED_PRODUCT_LEVEL`  
**Remediation class:** `ROLE_AWARE_HOME_DASHBOARD`  
**Domain change expected:** `False`  
**Evidence-backed findings:** 2  
**Observed modules:** Core / Home

The canonical Home prioritizes permission-safe destination links but does not summarize role-specific work, exceptions, activity or business attention signals.

Representative finding IDs: UIUX-F-065, UIUX-F-066

## RP-C21-SHARED-LABEL-OVERRIDE — بازنویسی برچسب دامنه توسط Component مشترک

**Status:** `CONFIRMED_SHARED_COMPONENT`  
**Remediation class:** `FIELD_LABEL_AUTHORITY_NORMALIZATION`  
**Domain change expected:** `False`  
**Evidence-backed findings:** 1  
**Observed modules:** Shared Forms

The shared form-field renderer substitutes labels by generic field name, overriding business-specific labels defined by individual forms.

Representative finding IDs: UIUX-F-073

## RP-C23-JALALI-INPUT-INCONSISTENCY — ناهماهنگی ورود تاریخ شمسی بین ماژول‌ها

**Status:** `CONFIRMED_MODULE_PATTERN`  
**Remediation class:** `CANONICAL_JALALI_DATE_COMPONENT`  
**Domain change expected:** `False`  
**Evidence-backed findings:** 2  
**Observed modules:** Billing

Some user-facing forms bypass the canonical Jalali input/parser pattern and expose native browser date controls.

Representative finding IDs: UIUX-F-083, UIUX-F-101

## RP-C24-PAGINATION-QUERY-STATE-LOSS — از دست رفتن وضعیت فیلتر و مرتب‌سازی هنگام صفحه‌بندی

**Status:** `CONFIRMED_SHARED_COMPONENT`  
**Remediation class:** `QUERY_STATE_PRESERVING_PAGINATION`  
**Domain change expected:** `False`  
**Evidence-backed findings:** 1  
**Observed modules:** Shared Tables

The shared pagination component replaces the query string with only the page parameter rather than preserving active filters/sort state.

Representative finding IDs: UIUX-F-085

## RP-C25-STATUS-SEMANTICS-INCOMPLETE — پوشش ناقص معنای وضعیت در Badge مشترک

**Status:** `CONFIRMED_SHARED_COMPONENT`  
**Remediation class:** `CENTRAL_STATUS_SEMANTIC_MAP`  
**Domain change expected:** `False`  
**Evidence-backed findings:** 1  
**Observed modules:** Shared Status Presentation

The shared status badge falls back to neutral for common domain lifecycle states because semantic mapping coverage is incomplete.

Representative finding IDs: UIUX-F-090

## RP-C26-JALALI-DISPLAY-INCONSISTENCY — ناهماهنگی نمایش تاریخ شمسی

**Status:** `CONFIRMED_SYSTEMIC`  
**Remediation class:** `CANONICAL_JALALI_DISPLAY`  
**Domain change expected:** `False`  
**Evidence-backed findings:** 2  
**Observed modules:** Equipment, Shared Date Presentation

User-facing dates are sometimes rendered through canonical Jalali filters and sometimes directly from raw Date/DateTime values.

Representative finding IDs: UIUX-F-091, UIUX-F-097
