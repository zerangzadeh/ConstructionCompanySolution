# BONIRA UI/UX Pilot Audit Checkpoint 01

## Baseline

`main @ 43ac319c6e73e48ca9626461b73987922c498ec3`

## Pilot status

The static inventory has been completed and the first audit-calibration pass has started.

- Static screen candidates catalogued: **383**
- Auxiliary/action routes retained: **221**
- Pilot-reviewed screen candidates in this checkpoint: **6**
- Confirmed pilot findings: **14**
- HIGH findings: **9**
- MEDIUM findings: **5**
- Findings currently requiring domain review: **0**

No remediation has been authorized or executed.

## Surfaces sampled

- shared authenticated context selector;
- Timekeeping calendar creation;
- Payroll workbench;
- Procurement RFQ buyer workspace;
- Parties governance list;
- Documents list;
- Subledgers workbench.

## What the pilot confirms

The earlier Product Owner concern is supported by baseline source evidence. The sampled UI repeatedly exposes internal/governance terminology, technical representations, and domain-command structures directly to end users.

The strongest confirmed patterns so far are:

1. technical/governance language leaking into operational UI;
2. workflow/domain commands presented without journey-oriented hierarchy;
3. technical identifiers or encoded values required as user input;
4. weak next-step guidance;
5. generic or governance-oriented action labels;
6. empty/state messaging that describes authorization scope rather than user task state.

These are still **pilot root-pattern candidates**. Full-audit frequency and module spread have not yet been counted.

## Important boundary

This checkpoint does not establish that business/domain architecture is defective.

For example, the RFQ source already limits the displayed actions to `actions` supplied by the backend. The UX finding is that allowed domain actions are rendered as equivalent buttons without stage/next-action guidance. The domain state machine must not be redesigned merely to fix that presentation problem.

Similarly, Subledgers resolves the submitted Treasury Movement ID against authorized posted movements. The UX defect is requiring the human to supply the raw identifier; the authority rule itself is not challenged by this finding.

## Next pilot work

Continue template/form/view sampling across:

- Home and global search;
- Projects list/detail/controls;
- Organization/member administration;
- Workforce/ESS;
- Inventory;
- Equipment/fixed assets;
- shared list/detail/create patterns.

Then calibrate the root-pattern catalogue before the full surface-by-surface audit.
