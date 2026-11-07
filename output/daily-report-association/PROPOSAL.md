# Daily Report record association — bounded proposal

The requested Create-page feature needs persisted associations. Existing SafetyIncident.daily_report and QualityIssue.daily_report fields are protected source context: reviewed records cannot change them and closed records cannot be saved. They are not general report-reference relations.

Proposed implementation:
- Add a report-owned reference table with organization, daily_report, exactly one safety_incident or quality_issue, created_by, created_at and a UUID identifier.
- Keep source record context, review state, workflow and finalized history unchanged. A record can be referenced by multiple reports without replacing its originating daily report.
- Allow selection only from records the actor can read, in the same tenant/project/site/phase as the report. Recheck access transactionally when the draft report is created.
- Retain notes. Add searchable multiple-record selectors, retain selections after errors, and show authorized linked records in Detail.
- Reuse existing DMS association services and related-documents components for existing documents and new uploads; require existing document permissions.
- Add an additive schema migration, service/HTTP authorization and isolation tests, and actual Chrome evidence.
- No production action, commit or push.

Decision: the user explicitly authorized this bounded extension in the asynchronous reply. Implementation and local development migrations are complete; see ../ui-remediation-20261105/REPORT.md. This authorization is not Product Owner visual acceptance.
