from pathlib import Path
exec((Path(__file__).parent.parent/"bonira-b03-01a1cbfa"/"browser.py").read_text(encoding="utf-8").rsplit("with sync_playwright() as pw:",1)[0])
targets=json.loads((root/db/"targets.json").read_text())
pks=json.loads((root/db/"review-delta.json").read_text())
decoy=json.loads((root/db/"context.json").read_text())
out=out/"review-authority"
out.mkdir(exist_ok=True)
with sync_playwright() as pw:
    browser=pw.chromium.launch(executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",headless=False)
    try:
        reviewer=connect(browser,"b02-field-reviewer")
        source=field+targets["observation"]+"/"
        for i,(w,h) in enumerate(widths.items()):
            reviewer.set_viewport_size({"width":w,"height":h})
            visit(reviewer,source)
            f=form(reviewer,f"/{pks[i*2]}/review/accept/")
            card=f.locator("..").locator("..")
            card.screenshot(path=out/f"proposal-control-{w}.png",animations="disabled")
            values=payload(f)
            wrong=send(reviewer,field+decoy["observation"]+f"/proposals/{pks[i*2]}/review/accept/",values)
            before=get("FieldDownstreamProposal",pk=pks[i*2])
            row("context_preserved",wrong==404 and before.status=="submitted",width=w,status=wrong)
            click(f)
            replay=send(reviewer,source+f"proposals/{pks[i*2]}/review/accept/",values)
            accepted=get("FieldDownstreamProposal",pk=pks[i*2])
            row("accept_final_endpoint",accepted.status=="accepted" and accepted.transitions.count()==2,width=w,replay=replay,audit=audit(accepted.pk),proposal=str(accepted.pk))
            f=form(reviewer,f"/{pks[i*2+1]}/review/reject/")
            fill(f,reason="نیاز به اصلاح پس از بررسی مستقل")
            values=payload(f)
            click(f)
            replay=send(reviewer,source+f"proposals/{pks[i*2+1]}/review/reject/",values)
            rejected=get("FieldDownstreamProposal",pk=pks[i*2+1])
            row("reject_final_endpoint",rejected.status=="rejected" and rejected.transitions.count()==2,width=w,replay=replay,audit=audit(rejected.pk),proposal=str(rejected.pk))
        (out/"results.json").write_text(json.dumps({"browser":browser.version,"results":results,"traffic":traffic},ensure_ascii=False,indent=2),encoding="utf-8")
    finally:
        browser.close()
assert all(x["match"] for v in results.values() for x in v)
