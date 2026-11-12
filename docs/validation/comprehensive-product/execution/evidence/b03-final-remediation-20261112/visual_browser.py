from pathlib import Path
exec((Path(__file__).parent.parent/"bonira-b03-01a1cbfa"/"browser.py").read_text(encoding="utf-8").rsplit("with sync_playwright() as pw:",1)[0])
targets=json.loads((root/db/"targets.json").read_text())
with sync_playwright() as pw:
    browser=pw.chromium.launch(executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",headless=False)
    reviewer=connect(browser,"b02-field-reviewer")
    visit(reviewer,field+targets["observation"]+"/")
    for w,h in widths.items():
        reviewer.set_viewport_size({"width":w,"height":h})
        card=form(reviewer,f'/{targets["proposals"][6]}/review/accept/').locator("..").locator("..")
        card.screenshot(path=out/f"proposal-control-{w}.png",animations="disabled")
    browser.close()
print("Read-only proposal control captures ready")
