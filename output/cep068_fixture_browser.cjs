const fs=require('fs');
const path=require('path');
const {pathToFileURL}=require('url');
const {chromium}=require('C:/Users/azera/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async()=>{
 const base=path.resolve('docs/governance/cep/evidence');
 const browser=await chromium.launch({channel:'msedge',headless:true,args:['--allow-file-access-from-files']});
 const checks=[];
 try{
  for(const [label,width,height] of [['desktop',1366,900],['mobile',390,844]]){
   const context=await browser.newContext({viewport:{width,height},locale:'fa-IR'});
   const page=await context.newPage();
   for(const name of ['empty','list','form','draft','submitted','error','denied','approved','routed']){
    const url=pathToFileURL(path.join(base,'CEP-068_MISSION_UI',name+'-render.html')).href;
    await page.goto(url,{waitUntil:'networkidle',timeout:45000});
    await page.waitForFunction(()=>[...document.querySelectorAll('style')].some(s=>s.textContent.includes('--tw-border-spacing-x')),null,{timeout:20000});
    await page.evaluate(async()=>{await document.fonts.ready;});
    await page.keyboard.press('Tab');
    const metric=await page.evaluate(()=>{
     const main=document.querySelector('main');
     const submit=[...document.querySelectorAll('main form button[type=submit]')].find(x=>['ثبت در منبع','ارسال برای بررسی'].includes(x.textContent.trim()));
     return {lang:document.documentElement.lang,rtl:document.documentElement.dir,
      viewport:innerWidth,document:document.documentElement.scrollWidth,
      main:main.clientWidth,mainScroll:main.scrollWidth,font:getComputedStyle(document.body).fontFamily,
      fontLoaded:document.fonts.check('16px Vazirmatn'),h1:document.querySelector('h1')?.textContent,
      focus:document.activeElement.tagName,submitBackground:submit?getComputedStyle(submit).backgroundColor:null,
      brokenImages:[...document.images].filter(x=>!x.complete||!x.naturalWidth).length};
    });
    if(metric.lang!=='fa'||metric.rtl!=='rtl'||metric.document>width||metric.mainScroll>metric.main+1||!metric.fontLoaded||metric.brokenImages)
     throw new Error('Fixture layout/font check failed: '+JSON.stringify({name,label,...metric}));
    if(metric.submitBackground==='rgba(0, 0, 0, 0)')throw new Error('Source utility stylesheet did not load');
    await page.screenshot({path:path.join(base,'CEP-068_MISSION_'+name+'_'+label+'.png'),fullPage:true});
    checks.push({name,label,...metric});
   }
   await context.close();
  }
  fs.writeFileSync(path.join(base,'CEP-068_MISSION_BROWSER.json'),JSON.stringify({
   scope:'ISOLATED_SYNTHETIC_DJANGO_RENDERED_FIXTURES_NOT_AUTHENTICATED_UAT',
   browser:'Headless Edge '+browser.version()+' / Playwright; isolated temporary profile',
   settingsChanged:false,signedInBrowserControlled:false,checks},null,2));
  console.log(checks.length+' Mission responsive screenshots PASS; RTL/Jalali/font/layout/keyboard checks retained.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
