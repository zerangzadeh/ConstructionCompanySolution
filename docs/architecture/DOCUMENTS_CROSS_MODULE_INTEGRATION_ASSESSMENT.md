# BONIRA — Documents Cross-Module Integration Assessment

**Assessment date:** 2026-11-03 (Asia/Tehran)  
**Scope:** Read-only architecture, integration, security-boundary and UX assessment of the current MVP surface.  
**Repository baseline:** `main`, HEAD and locally recorded `origin/main` = `560bc3c9f136a3b76c6816dc127a80d74bcb7a1d`. No remote fetch was performed.  
**Authority:** The Human request authorizes this report only; it does not authorize remediation, new relationships, migrations, production action or Git writes.

## 1. Conclusion and evidence limits

**The reported Project/Contract problem is real and is mainly a missing UI integration, rather than a missing document-storage or relationship capability.** Project, Contract, Estimate, Expense and Daily Report already have persisted, service-managed document relationships. Their ordinary Detail pages do not present a reusable related-document list or contextual association flow. Documents detail renders those relationships as text, without links back to their business records.

Project has an additional discoverability defect: its visible **«اسناد و گالری»** entry opens **«گالری تصاویر پروژه»**, which selects only `PHOTO` documents. Browser inspection found an empty gallery for a project whose non-photo documents were visible in Documents. This entry is not a general related-documents workspace.

The solution can predominantly reuse the existing **legacy-compatible DocumentLink plus domain-owned typed links, DMS services, protected delivery routes and shared templates**. It still needs application-layer selectors and contextual navigation/form plumbing; adding an include alone is insufficient. A universal attach-anything feature would require new domain capabilities for unsupported targets such as PR, PO, GRN, equipment and parties. Safety/Quality and RFQ require adapters to their existing exact-version evidence workflows, not generic DocumentLink substitutes.

### Evidence qualifications

- Findings describe the **current working tree**, including pre-existing uncommitted UI/view work. In particular, Project's current dashboard/gallery label is not a claim about pristine HEAD or a deployed release. Existing unrelated changes were preserved.
- The existing graph was queried for orientation. Current source, ORM model metadata and actual browser observations were used to establish findings; graph locations alone were not treated as proof. No graph rebuild was performed. The query tool's tracked cache-stamp side effect was restored.
- Live Chrome inspection used the existing authenticated local development session. A temporary development server was started after the initial localhost connection was refused. No authentication/role changes, uploads, links, submissions, archive operations, downloads, migrations, test fixtures or other business mutations were performed.
- **Live verification is partial.** Documents list/detail, Project detail/gallery and Contract detail were inspected. Estimate list was reached. Browser access then became disabled in Work settings. The remaining pages and security personas were not live-verified; source findings and proposed browser tests are explicitly distinguished below. Re-enabling was requested; no browser-access bypass was attempted.
- No application tests were run or authored. Existing tests were inspected, not represented as current PASS evidence. Downloads were not clicked because their handlers append audit events. No Human UAT, release PASS or security certification is claimed.

## 2. Current integration architecture

### 2.1 Document identity, binaries and metadata

`Document` is tenant-owned metadata: internal number, title, type, category, confidentiality classification, reference, description, expiry, archive fields and `current_version`. It does **not** contain a current Project or Contract FK. `DocumentVersion` stores immutable binary revisions, original filename, content type, size, SHA-256, uploader and version number. Its unique `(document, version_number)` constraint and service row lock support serial version allocation. The current version must belong to the document and be the latest revision.

`document_type=contract`, a title mentioning an incident, `reference`, OCR text, description, filename and confidentiality are **metadata**, not business links. In particular, the demo title «گزارش کنترل کیفیت مصالح» does not establish a QualityIssue relationship.

`PhotoMetadata` adds source/capture-time metadata to one PHOTO Document; it stores no separate binary or business target. `create_photo` creates real typed project/site/target associations. Gallery site context may also be derived from a Daily Report's site. That projection is not an additional persisted DocumentLink.

Sources: [models](../../apps/documents/models.py), [version/create services](../../apps/documents/services.py), [photo services](../../apps/documents/photo_services.py).

### 2.2 Two relationship representations coexist

`DocumentLink` has six nullable, explicit FKs: `project`, `contract`, `estimate`, `expense`, `payment`, `daily_report`. A database check requires exactly one target per row; conditional uniqueness prevents duplicate document/target pairs. Model validation checks common organization. Direct deletion is rejected at the application layer.

These are a **compatibility representation**, not the entire current integration surface. `DOCUMENT_LINK_TYPES` is a closed platform registry of domain-owned typed link models. For the six legacy-compatible types, DMS creation/link addition writes a compatibility row and a typed row in the same transaction, using the same UUID and retaining `legacy_link_id`. The historical backfill established that mapping; the retired Payment mapping now points to retained evidence in Documents, not a live payments domain. Other targets use typed rows without a generic DocumentLink row.

`typed_links_for_document` enumerates registered typed rows. DMS access checks use them, but the generic list/detail templates iterate **`document.links.all` only**. Thus an authorized typed-only association can affect access while being absent from the displayed relationship list. A template fix must not duplicate compatibility and typed rows.

Sources: [closed registry](../../apps/documents/link_registry.py), [typed-link base and compatibility model](../../apps/documents/models.py), [historical backfill](../../apps/documents/migrations/0006_p1_s20_typed_link_backfill.py), [retired Payment preparation](../../apps/documents/migrations/0012_legacy_payment_reference_preparation.py).

### 2.3 Actual registered target inventory

The following inventory is exhaustive for `DOCUMENT_LINK_TYPES` at assessment time. A registered target does not imply an exposed creation form, a business Detail page, or permission for arbitrary attachment changes.

| Registry key | Persisted typed model / target | Version semantics | Current product boundary / creation seam |
|---|---|---|---|
| `project` | `projects.ProjectDocumentLink.project` | Document/current history | MVP; generic DMS create/add-link and project photo upload; compatibility row |
| `project_site` | `projects.ProjectSiteDocumentLink.project_site` | Document/current history | MVP; service and photo flow; no generic DMS site control |
| `contract` | `contracts.ContractDocumentLink.contract` | Document/current history | MVP; generic DMS create/add-link; compatibility row |
| `estimate` | `estimates.EstimateDocumentLink.estimate` | Document/current history | MVP; generic DMS create/add-link; compatibility row |
| `expense` | `expenses.ExpenseDocumentLink.expense` | Document/current history | MVP; generic DMS create/add-link; compatibility row |
| `daily_report` | `daily_reports.DailyReportDocumentLink.daily_report` | Document/current history | MVP; generic DMS create/add-link; compatibility row |
| `material` | `materials.MaterialDocumentLink.material` | Exact `document_version` | MVP; DMS service support with `material_documents.link`; no visible generic target control |
| `field_observation` | `daily_reports.FieldObservationEvidenceLink.field_observation` | Exact version and hash | MVP namespace; domain evidence form/service, draft/capture restrictions; generic form declares field but templates omit it |
| `payment` | `documents.RetiredPaymentDocumentLink.payment` | Retained historical relationship | Historical only; no active Payment creation selector or settlement authority |
| `treasury_movement` | `treasury.TreasuryMovementDocumentLink.treasury_movement` | Document/current history | Finance UI-hidden in MVP; generic DMS still renders a treasury selector |
| `work_relationship` | `workforce.WorkRelationshipDocumentLink.work_relationship` | Document/current history | Workforce identity evidence; not a direct Person/Employee attachment target |
| `employee_qualification` | `workforce.EmployeeQualificationDocumentLink.qualification` | Exact version | Full-HR evidence route hidden in MVP |
| `employee_training` | `workforce.EmployeeTrainingDocumentLink.training_record` | Exact version | Full-HR evidence route hidden in MVP |
| `performance_evaluation` | `workforce.PerformanceEvaluationDocumentLink.performance_evaluation` | Exact version | Full-HR evidence route hidden in MVP |
| `payroll_inquiry` | `payroll.PayrollInquiryEvidenceLink.payroll_inquiry` | Exact version | Payroll hidden; generic DMS attachment addition explicitly denied; initial inquiry transaction owns attachment |
| `inspection` | `compliance.ComplianceEvidenceLink.inspection` | Exact version | Compliance hidden; sensitive evidence permission |
| `permit` | `compliance.ComplianceEvidenceLink.permit` | Exact version | Compliance hidden; sensitive evidence permission |
| `test` | `compliance.ComplianceEvidenceLink.test` | Exact version | Compliance hidden; not MVP QualityIssue |
| `test_result` | `compliance.ComplianceEvidenceLink.test_result` | Exact version | Compliance hidden; not MVP QualityIssue |
| `finding` | `compliance.ComplianceEvidenceLink.finding` | Exact version | Compliance hidden |
| `nonconformance` | `compliance.ComplianceEvidenceLink.nonconformance` | Exact version | Compliance hidden; separate from `quality.QualityIssue` |
| `capa_action` | `compliance.ComplianceEvidenceLink.capa_action` | Exact version | Compliance hidden |
| `partner_qualification` | `partner_qualification.PartnerEvidence.qualification` | Exact version | Partner qualification hidden; sensitive evidence permission |

### 2.4 Persisted relationships outside the generic registry

These real FKs were also verified against loaded Django model metadata. They must not be mistaken for arbitrary generic link support:

| Domain/model | Persisted relationship | Meaning for integration |
|---|---|---|
| Safety `SafetyReviewEvidence` | Review revision → DocumentVersion | Version-pinned submission evidence; `submit_safety_record(document_version_ids=...)` owns creation. Not a SafetyIncident target in DMS. |
| Quality `QualityReviewEvidence` | Review revision → DocumentVersion | Equivalent review-owned evidence for QualityIssue; separate from Compliance. |
| Procurement `QuoteRevisionEvidence` | Quote revision → Document + exact DocumentVersion + sealed custody | Governed supplier-original/attachment lineage. Internal custody and supplier portal upload exist. |
| Procurement `QuoteEvidencePackageFreezeItem` | Frozen package → exact DocumentVersion and evidence | Opening-package integrity evidence; not another user-editable link. |
| Contracts `ContractualRecordEvidence` | Contractual record → optional DocumentVersion or one other authoritative source | Real pinned evidence with a domain service; ordinary record UI lists evidence labels, without document navigation or an attachment-management form. |
| Billing `ContractGuarantee` | `evidence_document_version` | Versioned guarantee witness, selected through commercial evidence forms. |
| Billing `ContractComplianceEvidence` | `document_version` | Contract compliance/clearance witness; distinct from hidden Compliance app. |
| Billing `RetentionRelease` | `evidence_document_version` | Release witness; selected through its domain form. |
| Workforce `HRCertificateType`, `HRCertificateGeneration`, `EmploymentRecord` | Template/generated/employment DocumentVersion FKs | Specialized HR source and privacy contracts; full-HR surface hidden. |
| Commercial `TenderBidEvidence` | DocumentVersion | Hidden commercial domain. |
| Reporting `ReconciliationEvidenceLink`, `ProjectCloseoutEvidenceLink` | DocumentVersion | Hidden reporting evidence; projection authority only. |
| Support `SupportEvidence` | Document + DocumentVersion | Hidden support domain. |
| Knowledge `KnowledgeSourcePin` | Optional Document + DocumentVersion | Hidden knowledge/source-pinning domain. |

There is no generic PR, RFQ, PO, GRN, SafetyIncident, QualityIssue, Party, Equipment, Person, attendance or inventory-transaction target in the DMS registry. RFQ has the specialized quote association above. Equipment's `MaintenanceWorkOrderEvidence.reference`, meter/deployment evidence references, Expense `receipt_reference`/`source_reference`, Billing `PayableMeasurement.evidence_reference` and adjustment/evidence text are persisted **text references**, not DMS FKs. Do not resolve them by guessing IDs or matching names. A business record's Project/Contract FK likewise does not automatically link every document of that project/contract to the record.

Sources: [Safety review](../../apps/safety/record_review.py), [Quality review](../../apps/quality/record_review.py), [procurement models](../../apps/procurement/models.py), [contractual service](../../apps/contracts/contractual_services.py), [Billing models/forms](../../apps/billing/forms.py), [equipment reference model](../../apps/equipment/p8_models.py), [expense metadata](../../apps/expenses/models.py).

## 3. Coverage matrix — current MVP

**Reverse navigation** below means business page → authorized DMS detail/download, not an ORM reverse manager. **Bidirectional** requires a usable return route to the business object too. `B` = inspected live in this session; `S` = source inspected, live result unverified. A global sidebar link to Documents does not count as contextual reverse navigation.

| Entity | Link supported | Can users create/manage it? | Reverse navigation / bidirectional | UI availability and context | Gap |
|---|---|---|---|---|---|
| Project | Yes, compatibility + typed | DMS upload/add-link; gallery photo upload; additive only | General docs: no. Photo gallery: one-way to DMS; no DMS source return | **B** Detail has «اسناد و گالری»; gallery only photos, no general document count/list | Main UI gap; misleading label; Documents workspace does not filter to source project |
| Contract | Yes, compatibility + typed | DMS upload/add-link; no unlink/edit operation | No / no | **B** Detail has commercial sections but no related-document section | Main UI/navigation gap |
| Estimate | Yes, compatibility + typed | DMS upload/add-link | No / no | **S** Detail has no DMS panel; **B** list reached only | UI/navigation gap; existing contract context does not substitute for an estimate link |
| Daily Report | Yes, compatibility + typed | DMS upload/add-link | No on report Detail / no; project gallery can project its PHOTO links | **S** Detail has labor/material/activity/controls but no document section | UI gap; photo projection is not general attachment discovery |
| Expense / petty-cash expense record | Yes, compatibility + typed | DMS upload/add-link | No / no | **S** Detail has workflow/allocation sections; receipt reference is text | UI gap; receipt typing can be mistaken for attachment registration |
| Project Site | Yes, typed | Photo flow/service; no generic DMS site selector | No general-doc navigation / no | **S** Site list rather than a standalone site Detail route; project gallery offers site filtering | Existing capability needs a list-row or site-context gallery entry, not a fictitious Detail page |
| Field Observation | Yes, typed exact-version evidence | Domain form takes version UUID; capture + draft rules; generic target field omitted from templates | Evidence displayed but not openable / no | **S** Detail displays version UUID/hash and «شواهد DMS»; no document-title links | Severe UX/technical-label gap; preserve exact-version workflow |
| Material | Yes, typed exact-version evidence | DMS service accepts target with extra link permission; no ordinary UI picker/upload action | No / no | **S** Material Detail renders the material form; no related-doc panel | Application/UI gap; current service reusable, not a new relationship |
| Purchase Request (PR) | No direct DMS relation | No generic link action | No / no | **S** Detail navigates to RFQs, not documents | New bounded domain capability needed for direct attachments |
| RFQ | No generic target; quote evidence yes | Supplier portal and internal sealed-custody flows, not generic DMS association | Specialized buyer document delivery exists / no generic DMS return | **S** Detail hides buyer continuation in «سایر عملیات استعلام» → «ادامه مراحل پیشنهادها»; buyer workspace has per-evidence links when accessible | Existing specialized capability is indirect; never route sealed files through ordinary DMS |
| Purchase Order (PO) | No direct DMS relation | No | No / no | **S** Order Detail has no generic attachment capability | Backend/domain gap for direct attachments |
| Goods Receipt (GRN) | No direct DMS relation | No | No / no | **S** Receipt Detail has no generic attachment capability | Backend/domain gap; upstream RFQ evidence is not a receipt attachment |
| Safety Incident | Yes, review-revision DocumentVersion evidence only | Submission service supports evidence; ordinary incident UI does not expose that review-evidence input | No / no | **S** Operational Detail does not render review evidence | UI/application gap for existing review history; arbitrary incident attachment would be a new capability |
| Quality Issue | Yes, review-revision DocumentVersion evidence only | Equivalent review submission service; no ordinary UI evidence input | No / no | **S** Operational Detail does not render review evidence | Same distinction as Safety; do not reuse hidden Compliance targets |
| Contractual Record | Yes, domain-owned pinned evidence | Service exists; Detail shows labels, no association form/route | No openable document links / no | **S** «شواهد و تبار نسخه» exists | Existing read capability poorly surfaced; linking UI needs domain-service validation review |
| Guarantee | Yes, pinned version FK | Commercial create/revise forms choose an existing DMS version | No usable DMS link / no | **S** Detail renders witness UUID | Reuse existing evidence selector; replace raw ID display with authorized title/version navigation |
| Contract compliance / clearance evidence | Yes, pinned version FK | Domain create/revise form | No / no | **S** Shared commercial Detail renders witness UUID | UI gap, not the hidden Compliance domain |
| Retention Release | Yes, pinned version FK | Domain form chooses evidence | No general related-doc navigation / no | **S** Shared Detail emphasizes pinned clearance/reference fields rather than document navigation | Read adapter for existing witness; no financial-state changes |
| Progress Record, Progress Claim, Payable Measurement, Payable Certificate | No direct general DMS association | Evidence/reference text exists on some records; not DMS linking | No / no | **S** Business outputs and references are not attachments | New direct capability would need separate scope; contract documents may only be offered as explicitly labelled contract context |
| Field-worker Person / legacy Employee | No direct Person/Employee target; work-relationship and HR-source links exist | No generic field-worker document flow; HR upload route is MVP-hidden | No generic record-doc navigation / no | **S** Some employee HR evidence counts remain; hidden action routes are surface-checked | Do not expose full HR or infer identity. Any panel must follow explicit current identity/source authority |
| Equipment / maintenance work order | No DMS FK; reference-only evidence | UI can record a reference called «مرجع DMS/مدرک» | No verified DMS open / no | **S** Workbench labels reference counts «پیوست» and offers «افزودن پیوست» | Misleading attachment terminology; new true DMS relation needs authorization |
| Inventory / stock transaction | No direct DMS relationship | No | No / no | **S** Procurement/source relationships do not create document links | New capability if required |
| Attendance / timesheet / overtime | No direct DMS relationship | No generic action | No / no | **S** Separate workforce/timekeeping records | No automatic document association; new capability if required |
| Business Party | No direct DMS relationship | No generic action | No / no | **S** A contract's party is not a document target | New capability if required; preserve hidden partner qualification boundary |
| Project phase / WBS / activity; warehouse; service acceptance | No direct DMS relationship | No generic action | No / no | **S** Project/site, inventory or procurement context is not a direct attachment link | Separate authorization needed for a new direct target; do not infer association from shared project or source chain |

No assessed ordinary flow provides complete bidirectional, context-preserving integration. This is not a finding that every specialized module lacks evidence management: RFQ, photo and commercial evidence flows already supply important narrower capabilities.

## 4. Browser observations and reproducibility

The observations below are current-session UI evidence, not route-existence assumptions. URLs use placeholders to avoid copying internal identifiers or actor information into the report.

| ID | Browser path/action | Observed result | Verification limit |
|---|---|---|---|
| B01 | Open `/documents/` using existing local session | 9 documents listed across multiple projects despite a selected project in the shared context bar; generic creation entry present | One organization and existing account only; no cross-tenant/persona proof |
| B02 | Open a listed non-photo document's Detail | Relationships `project` and `payment` rendered as text; main content's only anchor was back to `/documents/`; version history visible | No mutation/download performed |
| B03 | Inspect that Detail's add-link area | Project, Contract, Estimate, Expense, Treasury Movement and Daily Report controls; no source-context breadcrumb; help says «دقیقاً یک target جدید انتخاب کنید.»; repeated expenses have indistinguishable description/amount labels | Options observed only; no submission |
| B04 | Open Project `PRJ-02-01` Detail | «اسناد و گالری» shown in local navigation and quick access; no general related-doc list/count | This page includes pre-existing working-tree UI changes |
| B05 | Follow its gallery entry | «گالری تصاویر پروژه», site/date filters and «افزودن تصویر»; empty-photo state even though non-photo project documents exist in Documents | Confirms photo-only mismatch, not absence of all project associations |
| B06 | Open Contract `CTR-02-03-04` Detail | Commercial overview, quantities, claims, progress, estimates and terms/activity sections; no document section or DMS link | Empty-vs-linked contract data was not changed to test rendering |
| B07 | Follow global Estimate entry | Estimate list accessible | Detail check interrupted when browser access was disabled |
| B08 | Inspect legacy relationship labels in Documents list/detail | English `Retired legacy Payment ... (UUID)` rendered; raw target codes visible in Detail | Technical leakage reproduced; historical relationship itself must remain intact |

Initial connection refusal was resolved by starting the normal local development server with `--noreload`; no database setup/migration was run. Later Work-setting denials prevented further UI inspection. Therefore upload preselection, the remaining entity Detail pages, mobile layout, restricted-persona behavior, sealed delivery, actual file responses and mutation journeys remain **unverified in this assessment**, even where source behavior is clear.

## 5. Security and lifecycle review

### 5.1 Authorization that a shared panel must preserve

- `OrganizationMiddleware` resolves the active organization from authenticated governed session state. Organization IDs in a target URL are not authority. DMS services require an active user and active, non-deleted organization and call business authorization; views also use active-organization/permission decorators.
- `get_organization_document` is tenant-filtered and invokes `_validate_document_context_access`. That routine rejects sealed supplier evidence, expired access, documents without typed links and inconsistent compatibility/typed link sets. It checks **every** linked target's tenant, target-view permission and project/site scope, plus applicable payroll inquiry/certificate privacy. One accessible Project link does not cancel an inaccessible second context.
- General document viewing, uploading/linking/version addition, downloading and archiving are distinct `documents.view`, `documents.upload`, `documents.download`, `documents.archive` capabilities. There is no general `documents.link` permission to invent. The generic HTTP add-link flow first resolves document view access as well as requiring upload. Material attachment additionally requires `material_documents.link`; field-observation linking requires capture authority and draft state.
- Adding links can **reduce** another user's document visibility because access intersects all contexts. DMS currently accepts separately authorized same-tenant contexts; it does not universally require all links to belong to one Project. A contextual UI must not silently add a Project link alongside an existing Contract link or infer a cross-project rule. Explain the selected association and preserve current semantics.
- Permission codes in template context are suitable for coarse visibility only. Object-specific action flags, titles, counts, selectors and links need server-side checks. A raw reverse-manager `.count()` would leak the existence of inaccessible documents and can disagree with the authorized list.

### 5.2 Important limits in the current boundaries

**Confidentiality is a closed classification field, not a demonstrated standalone clearance ACL.** Generic DMS access code validates/stores the classification but does not branch on INTERNAL/CONFIDENTIAL/RESTRICTED to require a separate clearance. The inspected confidentiality test verifies allowed values and tenant-owned category, not confidentiality-based exclusion. Sealed retention classification and employee category policy are separate enforced controls. Do not promise that a «محرمانه» badge alone restricts readers, invent a clearance hierarchy, or weaken existing source permissions. Any new confidentiality policy is separately governed security work.

`get_organization_documents` applies tenant, active-document, current-version, expiry, registered-link permissions and scope filtering, including specialized inquiry/certificate exclusions. It does **not literally execute every detail-level check**: legacy/typed parity and deleted linked-project validation occur in the detail validator. Consequently a new related-document count/list should use the canonical list as a candidate set and retain detail-equivalent authorization before exposing metadata, or factor an equivalent reusable selector after focused regression. Do not assume the list alone proves every candidate can open. This is a source-level parity risk, not an exploit proven by this browser session.

Safety/Quality review evidence submission validates same-tenant versions and active document/same-project context with `_valid_evidence_scope`, and requires document-view authority if evidence is supplied. That path is not the generic DMS detail/download validator and is not proof of present download authorization or a clean processing verdict. Contractual evidence addition similarly is not a replacement for DMS read/download checks. New presentation adapters must reauthorize current metadata/delivery without rewriting accepted evidence history. Any change to attachment acceptance rules needs its own bounded security review; this assessment does not change them.

### 5.3 Quarantine, history and delivery

- Generic upload accepts PDF/JPEG/PNG up to 10 MB, with extension/content-type/signature/size checks and SHA-256. Upload success does not imply malware-safe or immediately downloadable content. `DocumentVersion.is_available` requires the **latest** processing assessment to be CLEAN; unknown/error/unsupported/unsafe remain unavailable.
- Quarantined document metadata and its history can be visible to authorized viewers; download must remain unavailable. This should be reflected with Persian status text, not a broken link. A newly uploaded current version can be unavailable while an older version remains clean.
- General current-version and exact-version downloads resolve the authorized Document, require `documents.download`, enforce version/document/tenant consistency, check availability and append version-specific audit evidence. Protected storage refuses public `.url` access. File responses use attachment disposition and `nosniff`; photo preview adds private/no-store caching. Ordinary download response construction has no equivalent explicit Cache-Control assignment; cache behavior was not browser-tested.
- Pinned Material, Field Observation, Safety/Quality review, commercial and contractual witnesses must keep the referenced version. Do not replace a pinned download with `documents:download`, which serves the latest current version. Show «نسخه شاهد» separately from «نسخه جاری» when they differ.
- Archive preserves versions/links/audit but removes the document from ordinary active reads. There is no general unlink, replace-target, hard-delete, metadata-edit or restore UI contract in these routes. A shared panel must not offer them.
- RFQ quote delivery deliberately bypasses ordinary DMS through **its own stronger source authority**: RFQ scope, confidential quote-view permission, valid opening event, active exact-revision membership grant, frozen package readiness and delivered-byte hash verification. Generic DMS explicitly excludes sealed evidence even after it has an authorized specialized delivery route. Retain the buyer document route, original-file/attachment distinctions and revocation behavior; do not include sealed files or even unauthorized counts in a Project document panel.
- Employee DMS routes use explicit Person/WorkRelationship identity, current/history category policy and download policy, plus other linked-source checks. They are not generic access through Employee number/name/email. The current MVP route classifier hides the broader HR/ESS workspaces; no report recommendation reopens them.

Sources: [DMS services](../../apps/documents/services.py), [secure delivery views](../../apps/documents/views.py), [protected storage](../../apps/documents/storage.py), [employee access](../../apps/documents/employee_access.py), [RFQ opening/delivery](../../apps/procurement/opening_services.py), [buyer route](../../apps/procurement/rfq_actions.py), [current exposure authority](../../core/product_surface.py).

## 6. Root causes, duplicate entry and technical leakage

| Finding | Classification | Evidence and implication |
|---|---|---|
| F01 — No reusable business-object document projection | Application/UI integration | Core Detail views/templates do not request/render authorized related documents. Existing reverse FKs are not user navigation. |
| F02 — Photo-only destination presented as general documents | UI/label | Project dashboard links to `projects:gallery`; `get_project_photos` filters `document_type=PHOTO`. Confirmed B04–B05. |
| F03 — Compatibility-only relationship rendering | UI/read-adapter | `apps/documents/templates/documents/{list,detail}.html` iterate `document.links`, omitting typed-only context. |
| F04 — Context is not a DMS filter contract | Application/navigation | List accepts document/content/type/version filters, not business target filters; upload has no GET target preselection; success redirects to DMS detail and cancel to global list. Global project selector stays visible without controlling DMS rows. |
| F05 — Generic form and template capabilities diverge | UI/exposure | Form declares Field Observation but templates omit it; Treasury selector is rendered although Treasury is MVP-hidden. Permissions do not replace Product Surface gating. |
| F06 — Evidence references labelled as attachments | UI/domain distinction | Equipment has reference strings, not DMS links; Expense receipt reference and Billing evidence text can be mistaken for attached files. |
| F07 — Technical content leaks into ordinary UX | UI | Browser reproduced `project`, `payment`, `target`, retired-Payment English text/UUID. Source also shows Field Observation UUID/hash entry/list and commercial witness UUID-only display. |
| F08 — Unsupported targets cannot be fixed by template inclusion | Backend/domain | PR/PO/GRN/Equipment/Party etc. absent from generic target registry and FK inventory. RFQ's sealed quote evidence is a distinct existing exception. |
| F09 — List/detail authorization equivalence needs care | Security/application | Counts or selectors built from raw relations or only a coarse permission can reveal metadata or offer inaccessible rows. See section 5; no exploit claim. |

Users currently have to leave an object, find Documents globally, create a new Document, and manually choose the business target again; to attach an existing Document they must first find its DMS Detail and add another link there. This increases context mistakes and encourages duplicate uploads. Generic create requires exactly **one** target; selecting both Project and Contract is rejected, although users can later add another link. The UI does not explain clearly that linking a Contract already retains its project context without creating a direct Project association.

There is no binary deduplication contract demonstrated by computing SHA-256. Reference uniqueness is tenant-scoped for nonempty references, but a renamed/referenced copy can still become a new Document/version history. Reuse should offer **link existing** rather than reuploading. Repeated expense dropdown labels observed in B03 lack sufficient Project/date/reference context to disambiguate them. Do not silently merge histories or deduplicate by hash.

Historical retired Payment links must be preserved and displayed with a safe Persian historical label; do not expose a new Payment/settlement route. Changing presentation must not delete links or change their access contribution. Source UUIDs and hashes may remain internal audit evidence, but should not be required user input or default business labels.

## 7. Recommended reusable UX and placement

Follow [BONIRA UI standards](../ui-guidelines.md): Persian-first true RTL, Vazirmatn, compact enterprise surfaces, existing tokens/components, accessible status labels, Jalali dates, LTR isolation for numbers/file names, responsive layout and visible keyboard focus. Do not introduce a new frontend framework, custom attachment store or hidden-module entry point.

### Shared panel contract

- Heading **«اسناد مرتبط»** with the count of **distinct documents visible to this actor for this exact context**. For pinned evidence, identify the evidence revision and version; if useful show document count and evidence-version count separately. Never show total hidden/restricted counts.
- Compact initial list (for example five rows), title as the primary link, document type, current version or explicitly labelled pinned witness version, processing/access status, and optionally existing confidentiality label. Category/type/status must use Persian display labels. Do not invent an approved/rejected business status for a Document.
- Separate **«مشاهده»** and **«دریافت»**. Only render actionable delivery when exact document, version, download permission and availability checks pass. Display authorized quarantine metadata with «در انتظار ارزیابی ایمنی» or an appropriate supported verdict, without download. An expired/archived/inaccessible document contributes neither title nor count to the ordinary active panel.
- **«پیوند سند موجود»** only where an existing association service and required permissions/lifecycle support it. Use authorized title/number/type/version selection, never manual UUIDs. Do not offer unlink/reassign/delete actions.
- **«بارگذاری سند جدید»** where `create_document` or an existing domain-owned upload flow supports this target. Carry a server-resolved source context into the existing DMS form and explain which single target will be linked. Keep upload validation, processing and audit intact.
- **«مشاهده همه در اسناد»** for supported ordinary DMS contexts, with an explicit context chip and clear/remove-filter action. Preserve source breadcrumb/return navigation through list → detail → upload/add-link → success/cancel/validation error. These contextual query/return features are recommendations, **not existing contracts**.
- No DMS permission: omit protected metadata and document counts. No link/upload permission: read-only panel. Unsupported target: no enabled generic upload/link controls; do not present an empty attachment list that implies a supported relationship.

### Placement by applicable entity

| Entity | Recommended placement and allowed behavior |
|---|---|
| Project | Add a local «اسناد مرتبط» anchor and panel beside/below operational related records. Keep a separate correctly named «گالری تصاویر» entry. Initially show direct project links; do not silently aggregate all child-entity documents. Any later child projection must be separately labelled and preserve actual relationship provenance. |
| Contract | Add a local navigation anchor and panel near «شرایط و تغییرات قرارداد» / related estimates, before activity history. Direct contract links only; do not count every document in its Project. |
| Estimate | Panel below estimate identity/contract context and summary, before long item/history areas. Direct estimate links, not automatically all contract documents. |
| Daily Report | Panel after activity/observations and before lifecycle action footer. Reuse report links; photos can remain a type within that list with a separate gallery shortcut. |
| Expense | Panel beneath expense identity/workflow summary and before allocations. Distinguish attached receipt document from textual «مرجع رسید». |
| Site | Add a site-list-row/context action to the existing site-filtered gallery and, when implemented, a supported exact-site document view. There is currently no standalone site Detail page to modify. Reuse typed site links; do not invent a Site detail route merely for this task. |
| Material | Panel below material identity/form. Preserve exact `document_version`; link/upload requires both existing DMS and material-link permissions. An ordinary DMS current-version summary must not obscure the technical witness version. |
| Field Observation | Replace the UUID/hash-only evidence list with titles and pinned versions in its existing evidence section. Reuse domain attach service; show link-existing only while draft/capture-authorized. New-upload convenience requires an atomic adapter respecting the same draft/version rules. |
| Safety / Quality | Add **«شواهد بررسی رکورد»** within review history, showing persisted revision-specific evidence with authorized exact-version access. Do not add generic free attachment buttons to operational Detail. A later input flow must call the existing review submission service and preserve revision immutability. |
| Contractual Record | Upgrade existing «شواهد و تبار نسخه» rows to authorized source links, including exact-version document witnesses. Keep other source types as their own governed references. Do not invent an attachment form without the existing service's acceptance/authorization review. |
| Guarantee / contract compliance evidence / Retention Release | Replace UUID-only witness fields with the shared read-only pinned-document row. Retain domain create/revise forms for changing witnesses; do not add general add-link controls to finalized commercial records. |
| RFQ | Provide a clearer permitted entry to existing quote-review workspace near proposal workflow, with safe Persian wording. Retain per-quote evidence cards and existing buyer delivery. No general-DMS link, upload replacement or cross-quote count. |
| Field workforce / Employee | No broad MVP document panel merely because HR typed links exist. Preserve explicit identity/current source and MVP route boundaries; any read adapter must not activate hidden HR/ESS capabilities or qualification-management actions. |
| PR / PO / GRN / equipment / parties / inventory / timekeeping / claim and certificate records without direct links | No general Related Documents actions in the first reuse implementation. Correct misleading reference labels where bounded UI authorization permits. Treat true direct attachment support as future, separately authorized domain work. |

## 8. Minimal-reuse implementation approach and affected components

This is a proposed follow-up touch set, **not work performed by this assessment**.

1. Add a small, typed presentation/selector seam in Documents for supported business contexts. Resolve the target from the active organization and authorized source service/queryset; use an allowlist of existing target types. Start with Project, Contract, Estimate, Expense and Daily Report. Use typed links as the relationship source, deduplicate compatibility mirrors, intersect current DMS access, and return only safe document/view/download data. Validate counts against the same authorized result as the rows. Batch candidate queries/prefetches; the current generic validator enumerates registered link types per document, so avoid an unbounded N×registry query pattern.
2. Add a single reusable template such as `templates/components/related_documents.html` and a pinned evidence row variant. Reuse page header, status badge, form field/error, empty state and existing ERP surface/table styles. Domain views supply already-authorized DTO/context; no ORM/permission logic in templates and no generic domain mutations in the component.
3. Wire the five core Detail views/templates and Project dashboard navigation. Implement exact target filters in DMS list and target preselection in upload/add-link using server resolution. A query parameter conveys context, never authorization. Revalidate POST target and permissions in the existing atomic services. A fixed context must reject tampering. Preserve return context through form errors and completion using a validated local route/target descriptor, rather than blindly trusting `next` URLs.
4. Improve DMS relationship presentation using registry-backed, deduplicated rows with translated labels and authorized, Product-Surface-exposed source routes. Some targets have no Detail route; their adapter should supply an appropriate existing context/list destination or text, not fabricate an object URL. Keep legacy Payment as historical text. Remove MVP-hidden target controls through the centralized exposure policy while keeping backend contracts and historical links intact.
5. Add narrow read adapters for exact-version sources in a later bounded step. Keep Material/Field Observation, review evidence, commercial evidence and RFQ-specific ownership and route contracts distinct. Do not extend `DOCUMENT_LINK_TYPES` simply to make every card look uniform.

Likely affected existing files: `apps/documents/{services,link_registry,forms,views,urls}.py`; `apps/documents/templates/documents/{list,detail,upload}.html`; the five domains' Detail views/templates; `apps/projects/dashboard.py`; specialized evidence templates/views listed in the source index. Shared Product Surface helpers should be consumed, not replaced. No schema migration or new dependency is needed for the first five-entity navigation/panel implementation.

Key risks are count/title leakage, bypassing all-linked-context checks, silently moving pinned witnesses to the current version, sealed evidence exposure, hidden HR/finance activation, duplicate compatibility rows, cross-project context mistakes, open redirects, N+1 queries and accidentally treating a textual reference as an attachment. Current surrounding UI work also makes collision review necessary before any future implementation.

## 9. Prioritized remediation and acceptance criteria

| Priority / package | Scope | Acceptance criteria |
|---|---|---|
| P1-A — Correct misleading and technical presentation | Project gallery label, DMS relationship labels, retired Payment safe label, MVP-hidden Treasury control | Project photos are labelled «گالری تصاویر»; ordinary labels contain no raw target/model names, UUIDs or implementation terms; no new hidden-module URLs/actions; stored links and permissions unchanged. |
| P1-B — Core Related Documents read integration | Project, Contract, Estimate, Expense, Daily Report; shared selector/component; DMS source-return links | Each Detail shows distinct authorized count and rows for its exact persisted target; linked PDF discoverable from source; list count matches openable metadata; typed/legacy mirror appears once; authorized source return works; no changes to schemas or business transitions. |
| P1-C — Context-preserving association flows | Core five targets, existing create/add-link services | Authorized existing document can be linked without reupload; upload associates exactly the server-validated target; source context survives list/detail/errors/success/cancel; duplicate target is excluded/rejected without extra rows; no unlink/reassign action or new permission semantics. |
| P1-D — Security parity validation for new exposure | Shared selector/counts, all-context permissions, confidentiality claims, delivery | Actor without DMS/source scope sees no title/count/file metadata; stale/mismatched links fail closed; quarantine/expiry/archive and sealed rules hold; classification is not misrepresented as a clearance ACL. Any needed security behavior change is separately scoped before rollout. |
| P2-A — Existing typed/pinned evidence adapters | Material, Field Observation, Safety/Quality review history, contractual and commercial witnesses | Exact witness versions retained; manual UUID input replaced only through authorized selection; review/finalized history immutable; no generic attachment action on unsupported lifecycle states; source-specific checks preserved. |
| P2-B — Specialized discoverability | RFQ buyer evidence, Site context, reference-only attachment labels | RFQ users can find the existing permitted quote workspace; sealed bytes use existing buyer route only; Site navigation uses actual routes; Equipment reference counts/labels do not imply uploaded files. |
| P3 — New relationships only if separately authorized | PR/PO/GRN/equipment/party/etc. | Explicit owner, lifecycle, version semantics, required permissions, project/site rules, migration/backfill/compatibility plan and acceptance tests approved before implementing any new relation. No assumed change to financial/domain authority. |

P1 work should begin with read selectors and visibility validation before enabling mutation conveniences. P2/P3 are not automatically authorized by P1 completion or this report.

### Required follow-up browser and boundary tests

The following are **planned acceptance tests**, not results from this assessment. Mutation scenarios belong in an authorized isolated non-production test fixture, not the existing tenant used for read-only inspection.

| Test | Scenario and expected result |
|---|---|
| T01 — Five core entities | Link a PDF to each supported source. Open its Detail without using the global sidebar: correct count/title/type/version/status; open DMS Detail and return to the same source/context. Repeat with multiple relationships; direct-source panels must not infer child links. |
| T02 — Existing-document reuse | Choose «پیوند سند موجود»; search authorized documents by business labels; confirm linkage; one canonical Document and version history remain. Duplicate/retried submission produces no duplicate association. |
| T03 — Context preservation | Upload from each source, trigger required-field/file validation errors, cancel and succeed. Context remains correct at every step; success does not lose origin; no manual re-entry of source IDs. Changing/tampering target, organization, return path or hidden target type is rejected server-side. |
| T04 — Bidirectional navigation | DMS list/detail show deduplicated, translated actual contexts with only authorized/exposed source links. Historical Payment has safe text and no actionable retired route. Typed-only Material/Site/Observation contexts render accurately when their source is allowed. |
| T05 — Permission personas | Business-source reader without `documents.view`, DMS reader without source permission, read-only DMS user, uploader without source scope, project-only and site-only members: no unauthorized counts/titles/options; actions appear only when permitted and direct endpoints still deny forbidden requests. |
| T06 — Tenant and all-context scope | Two tenants with similarly named records; forged target/document/version IDs and context query/POSTs fail closed. One Document linked to both an allowed and denied context is absent, including from counts. Expired membership or organization suspension is rechecked before writes/delivery. |
| T07 — List/detail edge parity | Construct missing/mismatched compatibility rows and a deleted linked Project in isolated tests. Shared panel and filtered workspace must not leak metadata or advertise a row that detail denies. No repair/backfill is performed by a read selector. |
| T08 — Processing and download | Unknown/unsafe/unsupported/error current version: visible authorized status, no download. CLEAN version: authorized attachment response via application route; download audit references exact version. Later non-clean assessment removes availability. Direct storage/media URL never substitutes for delivery. |
| T09 — Version pinning | Link evidence to v1, append v2. Pinned rows/download still use v1, ordinary document rows identify current v2, and history is preserved. Version from another document/tenant is denied. Test clean old witness vs quarantined current version without changing pin. |
| T10 — Archive/expiry | Archived/expired documents disappear from active counts/lists; forged detail/download access fails closed. Evidence history is retained without exposing forbidden metadata. Test expiry between page rendering and click. |
| T11 — RFQ sealed exception | Before opening, without grant, after revocation, with wrong quote revision and with failed package readiness: no disclosure/count/bytes. Authorized opened exact revision works only through existing buyer route and still verifies pinned hash; ordinary DMS remains unavailable. |
| T12 — Domain lifecycle | Observation evidence addition only in authorized draft/capture state. Safety/Quality show revision-specific witnesses, not mutable general attachments. Commercial finalized records use domain revisions; ordinary generic add-link cannot replace witness history. |
| T13 — MVP exposure | MVP browser never offers Treasury, retired Payment, hidden Compliance/partner/Payroll/full-HR routes as new targets or source actions. FULL_ERP regression preserves those existing backend contracts; URL exposure still does not grant permissions. |
| T14 — Responsive/accessibility | At 390, 768 and 1440 px: RTL order, wrapped long titles, compact controls, no forced whole-page horizontal overflow, accessible status text and keyboard-visible focus. Persian labels/dates; filenames and version numbers isolated LTR; no UUID/hash/model/error leakage. |
| T15 — Context bar and performance | Explicit target filter is visible; global selected Project does not misleadingly imply a filter. Clear-filter behavior is predictable. Realistic multi-document fixtures show bounded query growth and pagination without unauthorized totals. |

Retain focused server-side tests alongside browser journeys for tenant/object authorization, atomic association/version operations, CSRF, safe return routes and exact-version delivery. Existing test sources worth reusing include `apps/documents/tests.py`, `test_cep079_form_scope.py`, `test_cep011.py`, `test_p1_s19_document_governance.py` and `test_p1_s21_processing.py`; their presence is not a current test execution result.

## 10. Source index and closeout

| Area | Primary inspected sources |
|---|---|
| DMS contracts and routes | [models](../../apps/documents/models.py), [registry](../../apps/documents/link_registry.py), [services](../../apps/documents/services.py), [forms](../../apps/documents/forms.py), [views](../../apps/documents/views.py), [URLs](../../apps/documents/urls.py), [storage](../../apps/documents/storage.py) |
| DMS presentation | [list](../../apps/documents/templates/documents/list.html), [detail](../../apps/documents/templates/documents/detail.html), [upload](../../apps/documents/templates/documents/upload.html) |
| Project/photo | [dashboard](../../apps/projects/dashboard.py), [views](../../apps/projects/views.py), [photo services](../../apps/documents/photo_services.py), [detail](../../apps/projects/templates/projects/detail.html), [gallery](../../apps/projects/templates/projects/gallery.html) |
| Core business pages | [Contract](../../apps/contracts/templates/contracts/detail.html), [Estimate](../../apps/estimates/templates/estimates/detail.html), [Daily Report](../../apps/daily_reports/templates/daily_reports/detail.html), [Expense](../../apps/expenses/templates/expenses/detail.html), [Material view](../../apps/materials/views.py) |
| Domain evidence | [Field Observation service](../../apps/daily_reports/field_services.py), [Field Observation UI](../../apps/daily_reports/templates/daily_reports/field_observation_detail.html), [Safety review](../../apps/safety/record_review.py), [Quality review](../../apps/quality/record_review.py), [contractual UI](../../apps/contracts/templates/contracts/contractual_record_detail.html), [commercial witness UI](../../apps/billing/templates/billing/commercial_record_detail.html) |
| Specialized quote delivery | [opening services](../../apps/procurement/opening_services.py), [RFQ actions](../../apps/procurement/rfq_actions.py), [RFQ Detail](../../apps/procurement/templates/procurement/rfq_detail.html), [buyer workspace](../../apps/procurement/templates/procurement/rfq_buyer_workspace.html) |
| Surface/identity/UI authority | [Product Surface](../../core/product_surface.py), [surface middleware](../../core/product_surface_middleware.py), [organization middleware](../../apps/organizations/middleware.py), [employee DMS](../../apps/documents/employee_access.py), [UI standard](../ui-guidelines.md), [D1–D7 strategy](PRODUCT_VISION_AND_MVP_RELEASE_STRATEGY.md) |

**Assessment disposition:** Source assessment and requested report delivered; live-browser coverage remains partial as explicitly recorded. All 58 local Markdown source links resolved and UTF-8 text had no replacement characters at closeout; focused whitespace validation passed. The temporary development server was stopped. Only this report is an intended persistent change; pre-existing and concurrent unrelated files were left alone. No product-code changes, migrations, commits or pushes were made. This report does not change live CEP Registry state or authorize its remediation plan.

**Final design conclusion:** Reuse existing DocumentLink/typed relationships and shared authorized UI components for the core problem. Add small contextual application adapters and navigation rather than a second DMS. Preserve specialized pinned/sealed evidence capabilities. New domain relationships are necessary only for currently unsupported direct targets, and require separate bounded authorization.
