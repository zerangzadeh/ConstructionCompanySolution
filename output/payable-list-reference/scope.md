# Payable Certificates List — bounded UI request
Authorization: user request 2026-11-01; no commit/push.
Branch main; HEAD and origin/main 5b760e853b329e2b03415da7b046641359db6a62.
Pre-existing dirty files preserved; Contracts list/components/styles are read-only references.
Touch set: billing/views.py (list context only), billing/payable_list.py, billing/templates/billing/payable_certificate_list.html, billing/static/billing/payable_list.css; focused list tests and this evidence directory.
Verification runner: scripts/verification/payable_list_validate.py; tests: apps/billing/test_payable_list.py.
No models, migrations, domain services, calculations, permission definitions, workflow, scope selector or Product Surface changes.
Filter options originate exclusively from the existing authorized certificate queryset. Invalid choices fail closed. Snapshot party and signed adjustment amounts are displayed unchanged. No mixed-currency financial aggregation.
Only existing secondary detail navigation is exposed, using the Contracts vertical menu pattern. No invented edit/delete/revision/export/print.
