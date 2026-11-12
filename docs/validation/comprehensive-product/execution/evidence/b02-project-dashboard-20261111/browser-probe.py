
import json, re, subprocess
from decimal import Decimal
from urllib.parse import parse_qs, quote, urlsplit
from django.conf import settings
from django.urls import reverse
from playwright.sync_api import sync_playwright
from apps.projects.models import Project, ProjectCostFact, ProjectCostFactKind, ProjectSite
from apps.contracts.models import Contract
from apps.daily_reports.models import DailyReport

os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"]="true"
cfg=json.loads((private/"actors.json").read_text())
out=Path(os.environ["BONIRA_DASHBOARD_EVIDENCE"])
base="http://127.0.0.1:"+(private/"web-port.txt").read_text().strip()
pid=cfg["projects"]["populated"]
route=lambda name,*args: reverse(name,args=args)
path=lambda key: route("projects:detail",cfg["projects"][key])
chars=str.maketrans("0123456789,.", "۰۱۲۳۴۵۶۷۸۹٬٫")
def persian(d):
    s=format(Decimal(str(d)),",f")
    return (s.rstrip("0").rstrip(".") if "." in s else s).translate(chars)
def snapshot():
    with connection.cursor() as cur:
        cur.execute("SET default_transaction_read_only=on")
    p=Project.objects.get(pk=pid,organization_id=cfg["organization"])
    costs=list(ProjectCostFact.objects.filter(project=p,kind__in=[ProjectCostFactKind.ACTUAL_RECOGNIZED,ProjectCostFactKind.ACTUAL_REVERSAL]).values_list("amount","currency"))
    contracts=list(Contract.objects.filter(project=p).values_list("status",flat=True))
    return {"budget":str(p.estimated_budget),"actual":str(sum(a for a,c in costs)),"currencies":sorted({c for a,c in costs}),"contracts":{s:contracts.count(s) for s in sorted(set(contracts))},"sites":ProjectSite.objects.filter(project=p).count(),"reports":DailyReport.objects.filter(project=p).count()}
def change_budget(amount):
    subprocess.run([sys.executable,str(private/"run.py"),str(private/"budget_variant.py"),amount],check=True)
def got(p, fragment, status=200):
    response=p.goto(base+fragment,wait_until="load",timeout=45000)
    assert response is not None and response.status==status,(fragment,response.status if response else None,p.url)
    return response
def login(b,key,js=True):
    ctx=b.new_context(java_script_enabled=js,viewport={"width":1440,"height":1000})
    ctx.route(re.compile(r"^https?://(?!"+re.escape(urlsplit(base).netloc)+r"(?:/|$))"),lambda r:r.abort())
    p=ctx.new_page()
    p.set_default_timeout(12000)
    got(p,route("accounts:login")+"?next="+quote(path("foreign" if key=="foreign" else "populated")))
    p.locator("[name=username]").fill(cfg["actors"][key])
    p.locator("[name=password]").fill(cfg["password"])
    with p.expect_navigation(wait_until="load",timeout=45000):
        p.locator('form button[type=submit]').click()
    assert urlsplit(p.url).path==path("foreign" if key=="foreign" else "populated"),p.url
    return p
def viewport(p,w,h):
    p.set_viewport_size({"width":w,"height":h})
def capture(p,label,width=None):
    p.evaluate("document.fonts.ready")
    m=p.evaluate("""() => ({
        viewport: innerWidth, doc: document.documentElement.scrollWidth, lang:document.documentElement.lang, dir:document.documentElement.dir,
        main:document.querySelectorAll('main').length, title:document.querySelector('main h1')?.innerText,
        headings:[...document.querySelectorAll('.project-dashboard h2')].map(e=>e.innerText),
        image:[...document.querySelectorAll('.project-hero img')].map(e=>({loaded:e.complete&&e.naturalWidth>0,alt:e.alt})),
        tabs:[...document.querySelectorAll('.erp-project-tabs a')].map(e=>({label:e.innerText,dest:e.pathname+e.search+e.hash})),
        kpis:[...document.querySelectorAll('#overview article')].map(e=>({key:e.dataset.kpiTone,text:e.innerText})),
        chart:[...document.querySelectorAll('#costs meter')].map(e=>e.value),
        compact:[...document.querySelectorAll('#overview article')].every(e=>e.scrollWidth<=e.clientWidth+1)
    })""")
    assert m["doc"]<=m["viewport"] and m["dir"]=="rtl" and m["main"]==1 and m["compact"],m
    if width: assert m["viewport"]==width
    f=label+".png"
    p.screenshot(path=out/f,full_page=True,animations="disabled",timeout=35000)
    m["screenshot"]=f
    return m
cases=[]
complete=False
def store():
    (out/"after.json").write_text(json.dumps({"chrome":b.version,"database":db,"profile":settings.PRODUCT_SURFACE_PROFILE,"status":"PASS" if complete else "IN_PROGRESS","cases":cases},ensure_ascii=False,indent=2),encoding="utf-8")
def check_cost(p,source,over=False):
    amounts=p.locator("#costs .project-budget__amounts").inner_text()
    budget,actual=map(Decimal,(source["budget"],source["actual"]))
    assert persian(budget) in amounts and persian(actual) in amounts,amounts
    comp=p.locator(".project-budget__result").inner_text()
    assert persian((actual*100/budget).quantize(Decimal("0.1")))+"٪" in comp and persian(budget-actual) in comp,comp
    expected_bars=[str((v*100/max(actual,budget)).quantize(Decimal("0.01"))) for v in (budget,actual)]
    assert [Decimal(p.locator("meter").nth(i).get_attribute("value")) for i in (0,1)]==list(map(Decimal,expected_bars))
    assert bool(p.locator(".project-budget__result--over").count())==over
    return {"amounts":amounts,"comparison":comp,"bars":expected_bars}
with sync_playwright() as pw:
    b=pw.chromium.launch(executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",headless=True)
    p=login(b,"owner")
    errors=[]
    http_errors=[]
    p.on("response",lambda r:http_errors.append({"status":r.status,"path":urlsplit(r.url).path}) if r.status>=400 and urlsplit(r.url).netloc==urlsplit(base).netloc else None)
    p.on("pageerror",lambda e:errors.append(str(e)))
    original=snapshot()
    print("Initial persisted read",original,flush=True)
    for w,h in ((1440,1000),(1024,820),(390,844)):
        viewport(p,w,h)
        got(p,path("populated"))
        cost=check_cost(p,original)
        tab=p.locator(".erp-project-tabs")
        assert tab.locator('[aria-current=location]').get_attribute("href")=="#overview"
        assert p.locator("header.project-hero").get_by_text("شرکت آزمایشی سپهر").is_visible()
        assert p.locator("header.project-hero").get_by_text("BUDGET").is_visible()
        assert p.locator("header.project-hero").get_by_text("فعال",exact=True).is_visible()
        assert p.locator("header.project-hero img").evaluate("(e)=>e.complete && e.naturalWidth>0")
        assert p.locator("#information a").count()==0
        controls=route("projects:controls",pid)
        assert p.locator("main").locator('a[href="'+controls+'"]').count()==1
        p.wait_for_function("!!Chart.getChart('project-contracts-chart')")
        chart=p.evaluate("Chart.getChart('project-contracts-chart').data.datasets[0].data")
        expected=[original["contracts"][s] for s in ("draft","active","completed","terminated")]
        assert chart==expected,(chart,expected)
        assert p.locator("#recent li").count()>=2
        assert p.locator("#related-documents").get_by_role("link",name="تصویر آزمایشی پیوست پروژه",exact=True).is_visible()
        assert p.locator('[data-kpi-tone=documents] bdi').inner_text()=="۱"
        for key,count in (("sites",original["sites"]),("reports",original["reports"]),("contracts",original["contracts"]["active"])):
            assert p.locator(f'[data-kpi-tone={key}] bdi').inner_text()==persian(count)
        case={"name":f"populated-{w}","source":original,"cost":cost,"contract_chart":chart,"view":capture(p,f"after-{w}",w),"actions":[]}
        for fragment in ("#information","#progress","#recent","#related-documents","#overview","#costs"):
            locator=tab.locator('a[href="'+fragment+'"]')
            locator.press("Enter")
            assert urlsplit(p.url).fragment==fragment[1:]
            p.wait_for_function("(href)=>document.querySelector('.erp-project-tabs a.is-current')?.getAttribute('href')===href",arg=fragment)
            assert p.locator(fragment).is_visible()
            case["actions"].append({"anchor":fragment,"active":True})
        p.locator(".erp-project-evidence summary").click()
        assert p.locator(".erp-project-evidence").get_attribute("open") is not None
        p.locator(".erp-project-evidence summary").click()
        cases.append(case);store()
    viewport(p,1440,1000)
    got(p,path("populated"))
    for tone in ("contracts","sites","reports"):
        link=p.locator(f"[data-kpi-tone={tone}] a")
        dest=link.get_attribute("href")
        assert dest
        with p.expect_navigation(wait_until="load",timeout=45000) as reply:
            link.click()
        assert reply.value and reply.value.status==200,(tone,p.url)
        assert p.locator("main h1").is_visible()
        if tone=="contracts": assert parse_qs(urlsplit(p.url).query).get("project_id")==[pid]
        if tone=="reports": assert parse_qs(urlsplit(p.url).query).get("project_filter")==[pid]
        if tone=="sites": assert pid in p.url
        cases.append({"name":"kpi-link-"+tone,"href":dest,"landing":p.url.removeprefix(base)})
        got(p,path("populated"))
    for selector,name in (
        ("#progress a","controls"),("#recent a","recent"),("#related-documents .erp-related-documents-name a","document"),
        (".erp-project-tabs a[href*='/gallery/']","gallery"),
    ):
        target=p.locator(selector).first
        dest=target.get_attribute("href")
        with p.expect_navigation(wait_until="load",timeout=45000) as reply:
            target.click()
        assert reply.value and reply.value.status==200,(name,p.url)
        cases.append({"name":"authorized-link-"+name,"href":dest,"landing":p.url.removeprefix(base)})
        got(p,path("populated"))
    for selector,name in (
        (".erp-project-tabs a[href*='/estimates/']","estimates"),
        (".erp-project-tabs a[href*='/billing/']","claims"),
        (".erp-project-quick a[href*='/workforce/']","workforce"),
        (".erp-project-quick a[href*='/timekeeping/']","timekeeping"),
    ):
        target=p.locator(selector).first
        dest=target.get_attribute("href")
        with p.expect_navigation(wait_until="load",timeout=45000) as reply:
            target.click()
        assert reply.value and reply.value.status==200,(name,p.url)
        assert pid in p.url,(name,p.url)
        cases.append({"name":"context-link-"+name,"href":dest,"landing":p.url.removeprefix(base)})
        got(p,path("populated"))
    download=p.locator("#related-documents").get_by_role("link",name=re.compile("دریافت سند"))
    response=p.request.get(base+download.get_attribute("href"))
    assert response.status==200 and response.body().startswith(b"\x89PNG")
    cases.append({"name":"protected-file","status":response.status,"content_type":response.headers["content-type"]})
    assert not errors,errors
    assert not http_errors,http_errors
    cases.append({"name":"local-page-health","javascript_errors":errors,"http_errors":http_errors})
    got(p,path("missing"))
    assert "داده در دسترس نیست" in p.locator("#costs").inner_text()
    assert not p.locator("#costs meter, .project-budget__result").count()
    assert p.locator(".project-hero__placeholder").is_visible()
    assert p.locator("#related-documents").get_by_role("status").is_visible()
    cases.append({"name":"budget-without-cost","view":capture(p,"empty-1440")})
    viewport(p,390,844)
    cases.append({"name":"budget-without-cost-mobile","view":capture(p,"empty-390")})
    got(p,path("zero"))
    assert "۰" in p.locator("#costs .project-budget__amounts dd").first.inner_text()
    assert not p.locator("#costs meter, .project-budget__result").count()
    cases.append({"name":"default-zero-budget-without-cost"})
    try:
        change_budget("5000000000")
        got(p,path("populated"))
        over=snapshot()
        cases.append({"name":"over-budget","source":over,"cost":check_cost(p,over,True),"view":capture(p,"over-budget-1440")})
        change_budget("0")
        viewport(p,390,844)
        got(p,path("populated"))
        no_budget=snapshot()
        assert persian(no_budget["actual"]) in p.locator("#costs").inner_text()
        assert "بودجه تخمینی مثبت ثبت نشده است." in p.locator("#costs").inner_text()
        assert not p.locator("#costs meter, .project-budget__result").count()
        cases.append({"name":"cost-with-zero-budget","source":no_budget,"view":capture(p,"zero-budget-390")})
    finally:
        change_budget(original["budget"])
    limited=login(b,"limited")
    viewport(limited,390,844)
    got(limited,path("populated"))
    assert not limited.locator("#costs, #progress, #related-documents, .project-hero img, .project-contracts").count()
    assert limited.locator('[data-kpi-tone=budget]').count()==1
    cases.append({"name":"limited-role","view":capture(limited,"restricted-390"),"direct_controls":limited.request.get(base+route("projects:controls",pid)).status})
    assert cases[-1]["direct_controls"] in {403,404}
    reader=login(b,"reader")
    assert reader.locator("#related-documents").is_visible() and not reader.locator(".project-hero img, #related-documents a[aria-label^='دریافت']").count()
    denied=reader.request.get(base+route("documents:photo-preview",cfg["photo"]))
    assert denied.status in {403,404}
    cases.append({"name":"document-read-without-download","preview_status":denied.status,"visible_documents":1})
    foreign=login(b,"foreign")
    denied=foreign.request.get(base+path("populated"))
    preview=foreign.request.get(base+route("documents:photo-preview",cfg["photo"]))
    assert denied.status in {403,404} and preview.status in {403,404}
    cases.append({"name":"foreign-tenant","dashboard_status":denied.status,"preview_status":preview.status})
    nojs=login(b,"owner",False)
    assert nojs.locator("#costs meter").count()==2
    assert persian(original["actual"]) in nojs.locator("#costs").inner_text()
    assert nojs.locator("#project-contracts-chart-values").is_visible()
    cases.append({"name":"javascript-disabled","cost_values_and_contract_legend":True})
    viewport(p,1440,1000)
    p.emulate_media(color_scheme="dark")
    got(p,path("populated"))
    colors=p.evaluate("() => ({background:getComputedStyle(document.querySelector('.project-hero')).backgroundColor, scheme:getComputedStyle(document.documentElement).colorScheme})")
    assert colors["background"]=="rgb(255, 255, 255)",colors
    cases.append({"name":"system-dark-preference","presentation":"existing light surface retained; no app dark theme implemented","colors":colors,"view":capture(p,"system-dark-preference-1440")})
    complete=True
    store()
    print(f"{len(cases)} Chrome cases passed. Chrome {b.version}.",flush=True)
    b.close()

