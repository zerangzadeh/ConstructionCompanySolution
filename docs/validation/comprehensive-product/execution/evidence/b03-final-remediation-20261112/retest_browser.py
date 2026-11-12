from pathlib import Path
exec((Path(__file__).parent.parent/"bonira-b03-01a1cbfa"/"browser.py").read_text(encoding="utf-8").rsplit("with sync_playwright() as pw:",1)[0])
targets=json.loads((root/db/"targets.json").read_text())
Audit=apps.get_model("audit.AuditEvent")
Item=apps.get_model("workflows.WorkItem")
def snapshot(p,name,w):
    p.set_viewport_size({"width":w,"height":{1440:900,1024:768,390:844}[w]})
    p.wait_for_timeout(80)
    info=p.evaluate("""()=>{const m=document.querySelector('main'); const visible=e=>!!e.getClientRects().length;const ids=[...m.querySelectorAll('[id]')].map(e=>e.id);return {width:innerWidth,document:document.documentElement.scrollWidth,dir:document.documentElement.dir,lang:document.documentElement.lang,duplicate_ids:ids.filter((v,i)=>ids.indexOf(v)!==i),headings:[...m.querySelectorAll('h1,h2')].map(e=>e.innerText),forms:[...m.querySelectorAll('form')].filter(visible).map(f=>({action:new URL(f.action).pathname,csrf:!!f.querySelector('[name=csrfmiddlewaretoken]'),buttons:[...f.querySelectorAll('button')].map(e=>e.innerText),fields:[...f.querySelectorAll('textarea,input:not([type=hidden]),select')].map(e=>({name:e.name,label:!!m.querySelector('label[for="'+e.id+'"]'),required:e.required}))}))}}""")
    png=f"{name}-{w}.png"
    p.screenshot(path=out/png,full_page=True,animations="disabled")
    pages.append({"name":name,"capture":png,**info})
    row("responsive",info["document"]<=w and not info["duplicate_ids"],page=name,width=w,document=info["document"],duplicate_ids=info["duplicate_ids"])
def audit_count(pk,action):
    return Audit.objects.filter(entity_id=str(pk),action=action).count()
def save(browser):
    (out/"results.json").write_text(json.dumps({"browser":browser.version,"results":results,"pages":pages,"traffic":traffic},ensure_ascii=False,indent=2),encoding="utf-8")
with sync_playwright() as pw:
    browser=pw.chromium.launch(executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",headless=False,args=["--no-first-run","--no-default-browser-check"])
    try:
        owner=connect(browser,"b02-owner")
        reviewer=connect(browser,"b02-field-reviewer")
        viewer=connect(browser,"b02-field-viewer")
        wrong=connect(browser,"b02-wrong-site")
        outsider=connect(browser,"b03-foreign")
        source=field+targets["observation"]+"/"
        for i,w in enumerate((1440,1024,390)):
            owner.set_viewport_size({"width":w,"height":900 if w==1440 else 768 if w==1024 else 844})
            reviewer.set_viewport_size({"width":w,"height":900 if w==1440 else 768 if w==1024 else 844})
            report=get("DailyReport",reporting_date=date(2026,9,i+1),site_id=ids["site"])
            url=daily+str(report.pk)+"/"
            visit(owner,url)
            f=form(owner,"/labor/")
            fill(f,team_name="گروه بازپخش نهایی",worker_count="4",hours_worked="6.50",notes="ثبت مصنوعی")
            values=payload(f)
            key=values["operation_key"]
            snapshot(owner,"labor-draft",w)
            click(f)
            first=report.labor_entries.get()
            before_audit=audit(first.pk)
            retry=send(owner,url+"labor/",values)
            conflict=send(owner,url+"labor/",{**values,"worker_count":"5"})
            concurrent=owner.evaluate("""async ({url,values})=>await Promise.all([1,2].map(()=>fetch(url,{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams(values),redirect:'manual'}).then(r=>r.type==='opaqueredirect'?302:r.status)))""",{"url":url+"labor/","values":values})
            row("0018_exact_retry",report.labor_entries.count()==1 and audit(first.pk)==before_audit,width=w,retry=retry,conflict=conflict,concurrent=concurrent,entry=str(first.pk),audit=before_audit)
            visit(owner,url)
            f=form(owner,"/labor/")
            fill(f,team_name="گروه بازپخش نهایی",worker_count="4",hours_worked="6.50",notes="ثبت مصنوعی")
            next_values=payload(f)
            click(f)
            row("0018_intentional_second",next_values["operation_key"]!=key and report.labor_entries.count()==2,width=w,rows=report.labor_entries.count())
            click(form(owner,"/submit/"))
            snapshot(owner,"daily-submitted-author",w)
            item=Item.objects.get(instance__subject_id=report.pk)
            before_item=(item.status,str(item.current_assignee_id))
            denied=send(owner,url+"approve/")
            report.refresh_from_db();item.refresh_from_db()
            row("0017_author_denied",denied==403 and not form(owner,"/approve/").count() and report.status=="submitted" and before_item==(item.status,str(item.current_assignee_id)) and not audit_count(report.pk,"daily_report.approved"),width=w,post=denied,status=report.status,item_status=item.status)
            no_new=send(owner,url+"labor/",{**values,"operation_key":str(uuid4())})
            replay=send(owner,url+"labor/",values)
            row("0018_finalized_retry",report.labor_entries.count()==2 and audit(first.pk)==before_audit,width=w,retry=replay,new_request=no_new)
            if i==0:
                for actor,p in (("viewer",viewer),("sibling",wrong),("foreign",outsider)):
                    status=send(p,url+"approve/")
                    row("0017_scope",status==403,actor=actor,status=status)
                    status=send(p,url+"labor/",values)
                    row("0018_scope",status==403,actor=actor,status=status)
            visit(reviewer,url)
            snapshot(reviewer,"daily-independent-review",w)
            click(form(reviewer,"/approve/"))
            report.refresh_from_db()
            row("0017_independent",report.status=="approved" and report.approved_by_id!=report.created_by_id and audit_count(report.pk,"daily_report.approved")==1,width=w,report=str(report.pk),audit=audit(report.pk))
            snapshot(reviewer,"daily-approved",w)
            # Existing source-only proposals, accepted and rejected through real controls.
            visit(reviewer,source)
            snapshot(reviewer,"proposal-review",w)
            accepted_id=targets["proposals"][i*2]
            rejected_id=targets["proposals"][i*2+1]
            proposal=get("FieldDownstreamProposal",pk=accepted_id)
            before={rel:model(rel).objects.count() for rel in ("DailyReport","DailyActivity","DailyReportEquipmentEntry","DailyReportMaterialEntry","DailyReportLaborEntry")}
            f=form(reviewer,f"/{accepted_id}/review/accept/")
            values=payload(f)
            if i==0:
                for actor,p in (("author",owner),("viewer",viewer),("sibling",wrong),("foreign",outsider)):
                    visit(p,source)
                    controls=main(p).locator('form[action*="/proposals/"][action*="/review/"]').count() if p.locator("main").count() else 0
                    denial=send(p,source+f"proposals/{accepted_id}/review/accept/",values)
                    proposal.refresh_from_db()
                    row("0019_scope",not controls and proposal.status=="submitted",actor=actor,post=denial,controls=controls)
                mismatch=send(reviewer,field+ids["sibling_observation"]+f"/proposals/{accepted_id}/review/accept/",values)
                row("0019_context",mismatch in (403,404),status=mismatch)
            click(f)
            retry=send(reviewer,source+f"proposals/{accepted_id}/review/accept/",values)
            proposal.refresh_from_db()
            row("0019_accept",proposal.status=="accepted" and proposal.reviewed_by_id!=proposal.created_by_id and proposal.transitions.count()==2 and audit_count(proposal.pk,"field.proposal_reviewed")==0,width=w,proposal=str(proposal.pk),retry=retry,audit=audit(proposal.pk),transitions=list(proposal.transitions.values("from_status","to_status","reason","proposal_hash")))
            f=form(reviewer,f"/{rejected_id}/review/reject/")
            reason=f.locator("[name=reason]")
            reason.fill("")
            button=f.locator("button[type=submit]")
            button.click()
            p2=get("FieldDownstreamProposal",pk=rejected_id)
            row("0019_reason_browser",reason.evaluate("e=>e.required&&!e.checkValidity()") and p2.status=="submitted",width=w)
            blank=send(reviewer,source+f"proposals/{rejected_id}/review/reject/",payload(f))
            p2.refresh_from_db()
            row("0019_reason_server",p2.status=="submitted",width=w,status=blank)
            reason.fill("نیاز به اصلاح شرح پیشنهاد")
            reject_values=payload(f)
            click(f)
            replay=send(reviewer,source+f"proposals/{rejected_id}/review/reject/",reject_values)
            p2.refresh_from_db()
            after={rel:model(rel).objects.count() for rel in before}
            visit(reviewer,source)
            row("0019_reject",p2.status=="rejected" and p2.transitions.count()==2 and before==after and not form(reviewer,f"/{rejected_id}/review/reject/").count(),width=w,retry=replay,proposal=str(p2.pk),audit=audit(p2.pk),transitions=list(p2.transitions.values("from_status","to_status","reason","proposal_hash")),source_only=before==after)
            snapshot(reviewer,"proposal-reviewed",w)
        save(browser)
    finally:
        save(browser)
        browser.close()
assert all(x["match"] for v in results.values() for x in v), "Inspect results for failed witness"
