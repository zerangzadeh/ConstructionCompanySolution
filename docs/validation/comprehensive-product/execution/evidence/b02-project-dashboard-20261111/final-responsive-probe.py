exec(compile((private/"after.py").read_text(encoding="utf-8-sig").split("with sync_playwright() as pw:")[0],str(private/"after.py"),"exec"))
with sync_playwright() as pw:
    b=pw.chromium.launch(executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",headless=True)
    p=login(b,"owner")
    source=snapshot()
    document=json.loads((out/"after.json").read_text(encoding="utf-8"))
    checks=[]
    for width,height,columns in ((1440,1000,6),(1024,820,3),(390,844,2)):
        viewport(p,width,height)
        got(p,path("populated"))
        check_cost(p,source)
        assert p.locator('[data-kpi-tone=cost] svg').evaluate('(e)=>getComputedStyle(e).color')=='rgb(245, 158, 11)'
        p.wait_for_function("!!Chart.getChart('project-contracts-chart')")
        assert p.evaluate("Chart.getChart('project-contracts-chart').data.datasets[0].data")==[1,3,1,1]
        actual_columns=p.locator("#overview").evaluate("(e)=>getComputedStyle(e).gridTemplateColumns.split(' ').filter(v=>parseFloat(v)>0).length")
        assert actual_columns==columns,(width,actual_columns)
        view=capture(p,f"after-{width}",width)
        matching=next(c for c in document["cases"] if c["name"]==f"populated-{width}")
        matching["view"]=view
        checks.append({"width":width,"kpi_columns":columns,"document_width":view["doc"],"status":"PASS"})
    viewport(p,1440,1000)
    p.emulate_media(color_scheme="dark")
    got(p,path("populated"))
    view=capture(p,"system-dark-preference-1440",1440)
    next(c for c in document["cases"] if c["name"]=="system-dark-preference")["view"]=view
    try:
        change_budget('5000000000')
        got(p,path('populated'))
        over=snapshot()
        check_cost(p,over,True)
        assert p.locator('.project-budget__result--over').evaluate('(e)=>getComputedStyle(e).backgroundColor') not in ('rgba(0, 0, 0, 0)','rgb(255, 255, 255)')
        view=capture(p,'over-budget-1440',1440)
        next(c for c in document['cases'] if c['name']=='over-budget')['view']=view
    finally:
        change_budget(source['budget'])
    (out/"after.json").write_text(json.dumps(document,ensure_ascii=False,indent=2),encoding="utf-8")
    (out/"final-responsive.json").write_text(json.dumps({"status":"PASS","chrome":b.version,"checks":checks},indent=2),encoding="utf-8")
    b.close()
    print("Final responsive pass: 3/3. KPI columns 6/3/2.")
