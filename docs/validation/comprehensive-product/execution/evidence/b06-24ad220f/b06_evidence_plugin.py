import os
from pathlib import Path

import pytest

root = Path(os.environ["B06_TMP"]) / os.environ.get("B06_PHASE", "original")
root.mkdir(exist_ok=True)

@pytest.fixture(autouse=True)
def isolate_evidence(request, monkeypatch):
    cls = request.cls
    if cls is None:
        return
    path = root / request.node.name
    if hasattr(cls, "evidence_root"):
        monkeypatch.setattr(cls, "evidence_root", path)
    if hasattr(cls, "browser_evidence_directory"):
        monkeypatch.setattr(cls, "browser_evidence_directory", path / "browser")
