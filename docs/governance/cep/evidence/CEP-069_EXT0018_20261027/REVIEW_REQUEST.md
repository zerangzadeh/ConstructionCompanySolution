# EXT-0018 — consolidated statutory review request

Package: `EXT0018-IR-1405-20261027-REVIEW-v1`,
[machine-readable intake](EXT0018_SOURCE_REVIEW_PACKAGE.json).
Cutoff: **2026-10-27 / 1405/08/05**. Status: **REVIEW PENDING; NOT ACTIVATED**.

## Decision required

Provide one accepted, attributable Payroll statutory currentness/applicability
review of this retained source bundle and its exact statutory-to-runtime mapping
for the intended non-production qualification population/periods. Record the real
reviewer, qualification, independence statement, review date, evidence reference,
scope, disposition and conditions. Reject or qualify any unsupported field; do
not approve a guessed default. No repository investigation is requested.

This is required by frozen PD-031, SPEC-030 (review/approval/evidence), and
CEP-069 §23 AC1 (reviewed official evidence). Recovered IMB-0083 additionally says
`Human Sign-off Required? YES`. The contract does **not** specify a mandatory
professional licence or invent a new reviewer appointment process. Existing
policy evidence requires qualification/independence information and an accepted
review; this packet records neither on someone else's behalf. Final Human
Sign-off/Production Certification is a separate, later decision.

## Already acquired — do not supply these again

The retained sources are from the government Laws and Regulations Portal, with retained text,
metadata, URLs, dates and SHA-256 in the machine-readable intake. These are
source acquisitions, not a current-law certification.

| Issuing authority | Exact document/version | Effective evidence and retained facts |
| --- | --- | --- |
| Parliament / President | 1405 Budget, adopted1404/12/25, promulgation203337 dated1404/12/26, Gazette23589 dated1404/12/28 | Official execution date1405/01/01. Consolidated portal version displays1405/04/10 amendment. |
| National Tax Administration | 200/1005/ص dated1405/01/31 | Annual1405 table:4800 million IRR exemption; five salary bands10/15/20/25/30 percent with source-native annual boundaries. No monthly conversion assumed. |
| Supreme Labour Council / Labour Ministry | 6682 issued1405/01/31, resolution1404/12/24 | Text expressly starts wage provisions at beginning1405. Daily floor5541850IRR; source-specific seniority/allowance/exception clauses preserved. |
| Social Security Organization | 1000/1405/493 dated1405/02/07 | Official effective1405/01/01; daily minimum5541850IRR; paragraph13 ceiling7times minimum and29/30/31-day distinction; worker-category exceptions retained. |
| National Tax Administration | 200/1405/59 dated1405/07/27 | Text replaces clause3 of prior200/1403/39 from issue date. Official original issued GIF retained. Portal body instead transcribes200/1406/39; original and transcription both retained for reconciliation. |
| Iranian legislature | Social Security Act, adopted1354/04/03, consolidated portal15217005284570186428 | Article28 and note1: insured7percent, employer20percent from1355, government3percent. Applicability/exceptions require accepted review; no government-share payer mapping assumed. |
| Parliament | Unemployment Insurance Act, adopted1369/06/26, portal1010273200061683763 | Article5 employer-paid3percent; article1 exclusions; article13 expressly starts at1369/05/06. No universal addition for excluded populations. |

The source bundle also retains the permanent Annual Budget Provisions Act,
adopted1404/09/30 (portal1903819389959200956), article1 clauses1/2, which the annual
table cites. Its official text includes annual exemption bands and multi-source
income. The consolidated Direct Taxes Act adopted1366/12/03
(portal892583840653829785), including articles82/83/84/85/86/91, is also retained;
its full rendered text supplements the abbreviated accessibility snapshot. The
older law's rates are not substituted for the annual1405 table. The annual Tax
circular portal warns that pages4/5 are illegible. The relevant
salary table is present in its text. No illegible content was reconstructed.
No source publication date is silently substituted for an execution date.
Where a source supplies no end date, it stays unspecified; a successor cannot
silently acquire an invented cutoff.

## Exact review matrix

| Item needing accepted interpretation | Evidence already supplied | Exact acceptance needed; currently absent |
| --- | --- | --- |
| Currentness and population | Five official annual/amendment sources, cutoff1405/08/05, exceptions preserved | Applicable employment/insurance classes; subsequent amendments or explicit currentness finding; treatment of housing changes flagged by SSO paragraph4. |
| Tax component classification and basis | INTA annual table rows1-1/2-1; amendment200/1405/59; acquired Direct Taxes Act82/83/84/91 | Taxable/non-taxable component mapping and basis factors; benefit/ordinary-limit/exemption applicability, including the amendment boundary. No Billing VAT mapping is reused. |
| Tax period / YTD | Annual exemption/bands in source units; acquired permanent Annual Budget Provisions1(1/2) and Direct Taxes Act86 | Accepted annual-to-period/cumulative method, multi-source income, opening/reset and YTD treatment. The current engine deliberately rejects `calculation_basis=cumulative`; a reviewer-required unsupported method cannot be replaced by dividing annual bands by12. |
| Insurance components / bases / shares | SSO493 paragraphs1/3/4/6-13, Social Security Act28 and note1, Unemployment Insurance Act1/5/13 | Applicable insurance class and shares, insured/non-insured components, exemption cases, period work-day basis and cap application; government contribution treatment. Base shares and unemployment law are already acquired, not requested again. |
| Rounding | Runtime supports ROUND_HALF_UP / ROUND_DOWN / ROUND_UP, scale0..8, stage=line | Source-backed applicable method, monetary precision and stage, or an explicitly authorized policy where law is silent. No choice made by Codex. |
| Retroactivity and supersession | Budget/SSO start1405/01/01; tax amendment starts issue date1405/07/27 | Treatment of already finalized periods and applicable correction dates; approved successor behavior. Existing runtime supports successor_only; no historical rewriting is authorized. |
| Output schema | Source-package envelope schema1 already implemented; official filing schemas are separately versioned policies | If actual filing/export is included, provide/qualify the applicable official INTA/SSO schema version and field/calendar mapping. CEP-069 does not acquire a new live-filing scope. Internal source-envelope version1 is not proof of a current official filing schema. |

These gaps are statutory interpretation/currentness inputs, not formatting,
hashing, fixture or migration tasks. The intake deliberately contains no accepted
review, no importable policy parameters and no activation actor. The exact
required runtime keys and existing limitations are supplied in the JSON and
implementation hashes; the reviewer need not derive them from repository code.

## Completion and blocking clauses

Canonical identity and six sealed recovery archives verified; retained evidence
inventory completed; current loopback Development inspected under SQL READ ONLY;
zero Payroll source packages/versions/accepted reviews; no pending migrations.
Both policy kinds reject missing sources at past/current/future cutoffs. Focused
synthetic qualification and its exact result are retained in FOCUSED_TESTS.txt
and FOCUSED_RESULT.json; these do not certify the official numbers above.

The missing accepted review and qualified mapping block **AC1** and the DoD
target outcome (official reviewed, versioned, effective-dated, explicitly activated
package). Actual official supersession/activation evidence for **AC4** is also
unavailable. AC2/3/5 preparation evidence is retained without converting the
required production-certification verification into a PASS. No runtime import or
activation occurred. GATE-08 remains PASS; GATE-11 remains NOT_PASSED.

After accepted review, Codex can construct the existing schema1 payloads, validate
exact policy parameters and source/review links, and perform authorized
non-production qualification. Any newly established unsupported statutory
semantics remain a precise governed finding, not implicit permission to redesign
Payroll. Production action and final Human certification/sign-off remain excluded.
