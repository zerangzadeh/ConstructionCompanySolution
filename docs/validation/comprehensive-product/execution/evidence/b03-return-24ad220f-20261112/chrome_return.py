import json
import os
from urllib.parse import urlsplit
from uuid import uuid4

os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"]="1"
from runtime_common import root, guard
from apps.audit.models import AuditEvent
from apps.daily_reports.models import DailyReport
from apps.daily_reports.submission_snapshots import digest
from apps.workflows.models import WorkflowInstance
from django.urls import reverse
from playwright.sync_api import sync_playwright

guard(readonly=True)
cfg = json.loads((root/"actors.json").read_text())
base = "http://127.0.0.1:"+(root/"web-port.txt").read_text().strip()
evidence = root/"chrome-accepted"
evidence.mkdir(exist_ok=True)
results=[]
widths={1440:900,1024:768,390:844}

def detail(pk):
    return reverse("daily_reports:detail", args=[pk])

def login(browser, role, width):
    ctx=browser.new_context(viewport={"width":width,"height":widths[width]}, accept_downloads=True)
    ctx.route("**/*", lambda route: route.continue_() if urlsplit(route.request.url).netloc==urlsplit(base).netloc else route.abort())
    p=ctx.new_page()
    p.set_default_timeout(20000)
    p.goto(base+reverse("accounts:login")+"?next=/daily-reports/")
    p.locator("[name=username]").fill(cfg[role])
    p.locator("[name=password]").fill(cfg["password"])
    click(p.locator("form").filter(has=p.locator("[name=password]")))
    assert urlsplit(p.url).path.startswith("/daily-reports/"), p.url
    return p

def click(form, button='button[type=submit]'):
    with form.page.expect_navigation(wait_until="domcontentloaded", timeout=35000):
        form.locator(button).first.click()
    form.page.wait_for_load_state("load")

def post(page, url, data):
    csrftoken=next(c["value"] for c in page.context.cookies() if c["name"]=="csrftoken")
    return page.request.post(base+url, form=data, headers={"X-CSRFToken":csrftoken}, max_redirects=0)

def form(page,suffix):
    return page.locator("main").locator(f'form[action$="{suffix}"]')

def capture(page, phase, w):
    metric=page.evaluate("""() => ({width:innerWidth, actual:document.documentElement.scrollWidth,
    dir:document.documentElement.dir, lang:document.documentElement.lang,
    duplicate_ids:[...document.querySelectorAll('main [id]')].map(x=>x.id).filter((x,i,a)=>a.indexOf(x)!==i)})""")
    assert metric["actual"]<=w and metric["dir"]=="rtl" and metric["lang"].startswith("fa"),metric
    assert not metric["duplicate_ids"],metric
    page.evaluate("document.activeElement.blur(); window.scrollTo(0,0)")
    page.wait_for_timeout(80)
    file=f"{phase}-{w}.png"
    page.screenshot(path=evidence/file, full_page=True, animations="disabled")
    return {"phase":phase,"path":urlsplit(page.url).path,"capture":file,**metric}

def snap(pk):
    report=DailyReport.objects.get(pk=pk, organization_id=cfg["organization"])
    return report

def row_state(report):
    return {
        "id":str(report.pk),"status":report.status,"revision":report.revision_number,
        "hash":report.submission_hash,"valid_hash":digest(report.submission_snapshot)==report.submission_hash,
        "author":str(report.created_by_id),"approver":str(report.approved_by_id) if report.approved_by_id else None,
        "work_item":str(WorkflowInstance.objects.get(subject_id=report.pk).work_items.get().pk),
        "actions":list(AuditEvent.objects.filter(entity_id=str(report.pk)).values_list("action",flat=True)),
    }

with sync_playwright() as pw:
    browser=pw.chromium.launch(executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",headless=True,args=["--no-first-run","--no-default-browser-check"])
    try:
        for width, first_id in zip(widths,cfg["reports"]):
            author=login(browser,"author",width)
            reviewer=login(browser,"reviewer",width)
            a=detail(first_id)
            author.goto(base+a)
            click(form(author,"/submit/"))
            first=snap(first_id)
            assert first.status=="submitted" and first.submission_hash
            original_hash=first.submission_hash
            assert not form(author,"/return/").count()
            assert post(author,a+"approve/",{}).status==403
            reviewer.goto(base+a)
            bad=post(reviewer,a+"return/",{"reason":"   ","operation_key":str(uuid4())})
            assert bad.status==400 and snap(first_id).status=="submitted"
            f=form(reviewer,"/return/")
            f.locator('[name="reason"]').fill("اصلاح شرح و ردیف‌های گزارش")
            reason_payload=f.evaluate("(f)=>Object.fromEntries(new FormData(f))")
            pages=[capture(reviewer,"return",width)]
            click(f)
            assert snap(first_id).status=="returned"
            assert post(reviewer,a+"return/",reason_payload).status==302
            assert post(reviewer,a+"return/",{**reason_payload,"reason":"دلیل دیگر"}).status==409
            assert not form(reviewer,"/correction/start/").count()
            author.goto(base+a)
            click(form(author,"/correction/start/"))
            second_id=DailyReport.objects.get(previous_revision_id=first_id).pk
            draft=detail(second_id)+"correction/"
            assert urlsplit(author.url).path==draft
            header=author.locator("[data-correction-header]")
            header.locator('[name="work_performed"]').fill("شرح جدید آزمایشی نسخه دوم")
            click(header)
            fields={"labor":"team_name","equipment":"equipment_name","materials":"material_name","activities":"description","delays":"cause"}
            for kind,field in fields.items():
                author.locator(f'a[href*="/correction/{kind}/"]:not([href$="/add/"])').first.click()
                author.wait_for_load_state("load")
                entry=author.locator("[data-correction-entry]")
                entry.locator(f'[name="{field}"]').fill({"labor":"گروه اصلاح‌شده","equipment":"تجهیز اصلاح‌شده","materials":"مصالح اصلاح‌شده","activities":"فعالیت اصلاح‌شده","delays":"علت اصلاح‌شده"}[kind])
                click(entry)
                assert urlsplit(author.url).path==draft
            pages.append(capture(author,"correction",width))
            submit=form(author,"/correction/submit/")
            submit_payload=submit.evaluate("(f)=>Object.fromEntries(new FormData(f))")
            click(submit)
            assert snap(second_id).status=="submitted"
            assert post(author,draft+"submit/",submit_payload).status==302
            reviewer.goto(base+detail(second_id))
            pages.append(capture(reviewer,"resubmitted",width))
            click(form(reviewer,"/approve/"))
            assert snap(second_id).status=="approved"
            assert reviewer.locator('a[href="'+a+'"]').count()>=1
            reviewer.goto(base+a+"?format=print")
            assert "شرح اولیه آزمایشی" in reviewer.locator("body").inner_text()
            assert "شرح جدید آزمایشی نسخه دوم" not in reviewer.locator("body").inner_text()
            pages.append(capture(reviewer,"history-print",width))
            first=snap(first_id)
            second=snap(second_id)
            assert first.submission_hash==original_hash and first.status=="returned"
            assert first.submission_snapshot["entries"]["labor"][0]["team_name"]=="تیم الف"
            assert second.submission_snapshot["entries"]["labor"][0]["team_name"]=="گروه اصلاح‌شده"
            result={"width":width,"pages":pages,"source":row_state(first),"successor":row_state(second),
                    "empty_reason_http":bad.status,"edited_entry_families":list(fields)}
            assert result["source"]["valid_hash"] and result["successor"]["valid_hash"]
            assert result["source"]["work_item"] != result["successor"]["work_item"]
            results.append(result)
            (evidence/"results.json").write_text(json.dumps({"chrome":browser.version,"journeys":results},ensure_ascii=False,indent=2),encoding="utf-8")
            print("Verified width",width,flush=True)
            author.context.close()
            reviewer.context.close()
    finally:
        browser.close()
assert len(results)==3
