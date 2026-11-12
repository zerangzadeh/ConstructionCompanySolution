from pathlib import Path
exec((Path(__file__).parent.parent/"bonira-b03-01a1cbfa"/"browser.py").read_text(encoding="utf-8").rsplit("with sync_playwright() as pw:",1)[0])
targets=json.loads((root/db/"targets.json").read_text())
decoy=json.loads((root/db/"context.json").read_text())
with sync_playwright() as pw:
    browser=pw.chromium.launch(executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",headless=False)
    reviewer=connect(browser,"b02-field-reviewer")
    source=field+targets["observation"]+"/"
    visit(reviewer,source)
    pk=targets["proposals"][6]
    f=form(reviewer,f"/{pk}/review/accept/")
    status=send(reviewer,field+decoy["observation"]+f"/proposals/{pk}/review/accept/",payload(f))
    proposal=get("FieldDownstreamProposal",pk=pk)
    row("0019_same_site_wrong_context",status==404 and proposal.status=="submitted" and proposal.transitions.count()==1,status=status,proposal=str(proposal.pk),observation=targets["observation"],requested_observation=decoy["observation"],audit=audit(pk))
    (out/"context-result.json").write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding="utf-8")
    browser.close()
assert all(x["match"] for v in results.values() for x in v)
