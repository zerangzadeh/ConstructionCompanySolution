# Attributable iteration record

- Initial conditional-decision safety delta: 5/5 PASS; database removed.
- First remediation run: 35 cases, 12 failed because the isolated test
  configuration did not preserve the Development-only settings guard. The test
  settings were corrected; the production guard was retained.
- Second remediation run: 34/35 PASS; adopted conditional-review reference was
  excluded from known schema1 evidence references. Added the retained adopted
  review to the package snapshot/reference validation, while keeping an accepted
  technical review mandatory. Conditional approval alone still cannot import.
- Subsequent remediation run: 35/35 PASS. Added chronological/local-prior
  reconciliation protection and its focused regression before final closeout.
- Initial fresh source qualification: synthetic fixture attempted a second
  regular run in the same period. The database rejected it. Corrected the
  fixture to the existing off-cycle/replacement model; no constraint weakened.
- Repaired qualification: explicit import/activation, native statutory
  calculation, housing delta/replacement, effective-date history, migration
  apply/rollback/reapply and database removal PASS.

All failures were attributable implementation/test/evidence issues and repaired
under the explicit Human instruction. No pre-existing test failure was waived.
Final outputs, not this iteration log, define the measured final result.
