"""Repeat the affected set, confining synthetic uploads and preserving old traces."""
import json
import os
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[3]
os.chdir(root)
sys.path.insert(0, str(root))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
import django
django.setup()
from django.test import override_settings
import pytest

original = json.loads((root / "output/mvp-02/VALIDATION.json").read_text(encoding="utf-8"))
args = original["automated_tests"]["argv"][3:]
args.insert(0, "apps/workforce/test_mvp02_uiux.py")
(root / "output/mvp-02/uiux/affected-test-argv.json").write_text(json.dumps(args, indent=2), encoding="utf-8")
traces = {p: p.read_bytes() for p in (root / "docs/governance/cep/evidence").glob("CEP-062_*TRACE.json")}
try:
    with override_settings(MEDIA_ROOT=root / "output/mvp-02/uiux/test-media"):
        result = pytest.main(args)
finally:
    for path, content in traces.items():
        path.write_bytes(content)
raise SystemExit(result)
