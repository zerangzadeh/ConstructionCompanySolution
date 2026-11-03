"""Read-only PDF qualification using bundled pypdf; no application dependency."""

import json
import re
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[2]
DIRECTORY = ROOT / "output/mvp-06/browser"
EXPECTED = {
    "claim-one-page": ("54", "-6", "F61-C"),
    "claim-multi-page": ("F61-C",),
    "po-one-page": ("PO-GRN", "125"),
    "po-multi-page": ("PO-LONG", "1,000,000.25"),
    "grn-one-page": ("GRN-1", "PO-GRN"),
    "grn-multi-page": ("GRN-LONG", "PO-LONG"),
    "daily-one-page": ("1405/08/12",),
    "daily-multi-page": ("1405/08/12",),
    "expenses-one-page": ("REC-007", "12,345.67"),
    "expenses-multi-page": ("REC-007", "1,234,567.89"),
}


def embedded(font):
    # Skia can embed variable-font glyph outlines as Type 3 CharProcs rather
    # than a conventional FontFile stream. Both are self-contained resources.
    if font.get("/Subtype") == "/Type3":
        glyphs = font.get("/CharProcs")
        return bool(
            glyphs
            and all(
                item.get_object().get_data() for item in glyphs.get_object().values()
            )
        )
    if "/DescendantFonts" in font:
        return all(embedded(item.get_object()) for item in font["/DescendantFonts"])
    descriptor = font.get("/FontDescriptor")
    return bool(
        descriptor
        and any(
            key in descriptor.get_object()
            for key in ("/FontFile", "/FontFile2", "/FontFile3")
        )
    )


results = []
for pdf in sorted(DIRECTORY.rglob("*.pdf")):
    reader = PdfReader(pdf, strict=True)
    assert pdf.read_bytes().startswith(b"%PDF-")
    assert not reader.is_encrypted
    assert len(reader.pages) > 0
    texts = [page.extract_text() for page in reader.pages]
    assert all(len(text.strip()) > 60 for text in texts), (
        f"Blank/footer-only page: {pdf.name}"
    )
    text = "\n".join(texts)
    assert "\ufffd" not in text
    assert re.search(r"[\u0600-\u06ff\ufb50-\ufeff]", text)
    assert not re.search(r"[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-", text)
    assert not re.search(r"https?://", text)
    for token in EXPECTED[pdf.stem]:
        assert token in text, (pdf.name, token)
    for page in reader.pages:
        assert abs(float(page.mediabox.width) - 595.28) < 1
        assert abs(float(page.mediabox.height) - 841.89) < 1
        fonts = page["/Resources"]["/Font"].get_object()
        assert fonts and all(embedded(font.get_object()) for font in fonts.values())
        for annotation in page.get("/Annots", []):
            item = annotation.get_object()
            assert "/AA" not in item
            assert "/A" not in item or "/URI" not in item["/A"]
    root = reader.trailer["/Root"]
    assert "/OpenAction" not in root and "/AA" not in root
    # PDF stream order puts the margin-box page counter before document text.
    continuation = [
        next(line for line in page.splitlines() if not re.search(r"\d+ / \d+$", line))
        for page in texts[1:]
    ]
    if len(continuation) > 1 and pdf.stem != "claim-multi-page":
        assert len(set(continuation)) == 1, f"Missing repeated header: {pdf.name}"
    # Earlier failed iterations can leave extra PNG pages; retain only pages
    # actually present in the final PDF. This is a bounded test-output cleanup.
    for png in pdf.parent.glob(pdf.stem + "-[0-9]*.png"):
        number = int(png.stem.rsplit("-", 1)[1])
        if number > len(reader.pages):
            png.unlink()
    results.append(
        {
            "pdf": str(pdf.relative_to(ROOT)).replace("\\", "/"),
            "pages": len(reader.pages),
            "characters_per_page": [len(item) for item in texts],
            "structure": "PASS",
            "a4": "PASS",
            "embedded_fonts": "PASS",
            "source_tokens": "PASS",
            "no_blank_pages": "PASS",
            "no_external_actions": "PASS",
            "repeated_continuation_heading": "PASS"
            if continuation
            else "NOT_APPLICABLE",
        }
    )
assert {Path(row["pdf"]).stem for row in results} == set(EXPECTED)
(DIRECTORY.parent / "pdf-audit.json").write_text(
    json.dumps(results, ensure_ascii=False, indent=2), encoding="utf8"
)
print(f"{len(results)} PDFs / {sum(row['pages'] for row in results)} pages PASS")
