# Recheck procedure

These are the exact verification scripts used for the final remediation. They import the private `browser` helper and synthetic fixture manifest retained locally under `.scratch/project-detail-ui-remediation/`; credentials, cookies, settings, uploaded files and the manifest are intentionally excluded from published evidence. Run only against that isolated loopback validation cluster, never a development business or production database.

```powershell
. .scratch/project-detail-ui-remediation/env.ps1
$env:PYTHONUTF8='1'
$env:UI_DB='project_ui_retest'
.venv/Scripts/python.exe -m pytest apps/projects/test_project_operations_dashboard.py apps/projects/test_command_center.py apps/projects/test_photo_gallery.py --reuse-db -q
.venv/Scripts/python.exe .scratch/project-detail-ui-remediation/verify_browser.py
.venv/Scripts/python.exe .scratch/project-detail-ui-remediation/equipment_final.py
.venv/Scripts/python.exe .scratch/project-detail-ui-remediation/protected_retest.py
.venv/Scripts/python.exe .scratch/project-detail-ui-remediation/business_snapshot.py
.venv/Scripts/python.exe .scratch/project-detail-ui-remediation/preservation.py
```

Chrome uses `channel='chrome'`, not the bundled Chromium. Each responsive loop explicitly sets 1440×900, 1024×768 and 390×844. Screenshot capture uses those viewports and saves the full document. Before capture ran against the entry implementation, before product mutation. After capture ran against the final implementation with identical prepared business fixtures. The database clone names and fixture preparation are documented in the report. The private cluster is stopped at closeout; restarting it requires its saved loopback port and `max_locks_per_transaction=256`.
