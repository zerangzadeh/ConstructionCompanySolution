// Compare measured DOM styling/geometry from before and offline Chrome runs.
const fs = require('node:fs');
const crypto = require('node:crypto');
const path = require('node:path');
const [beforeDirectory='output/f1/before',afterDirectory='output/f1/offline',outputDirectory='output/f1'] = process.argv.slice(2);
const before = JSON.parse(fs.readFileSync(path.join(beforeDirectory,'results.json'),'utf8'));
const after = JSON.parse(fs.readFileSync(path.join(afterDirectory,'results.json'),'utf8'));
const props=['display','position','direction','fontFamily','fontSize','fontWeight','lineHeight','color','backgroundColor','borderTopWidth','borderTopColor','borderRadius','paddingTop','paddingRight','paddingBottom','paddingLeft','marginTop','marginRight','marginBottom','marginLeft','gap','gridTemplateColumns','boxShadow','overflowX'];
const pages = after.results.map(page => {
  const old = before.results.find(p=>p.name===page.name);
  if (!old) throw new Error('Missing baseline: '+page.name);
  const diffs=[];
  const a=old.state.visual,b=page.state.visual;
  if(a.length!==b.length) diffs.push({type:'node-count',before:a.length,after:b.length});
  for(let i=0;i<Math.min(a.length,b.length);i++) {
    if(a[i].tag!==b[i].tag || a[i].class!==b[i].class) diffs.push({index:i,type:'structure',before:a[i].class,after:b[i].class});
    else {
      const changed=props.filter((p,j)=>a[i].style[j]!==b[i].style[j]);
      if(changed.length) diffs.push({index:i,class:a[i].class,type:'style',properties:changed.map(p=>({property:p,before:a[i].style[props.indexOf(p)],after:b[i].style[props.indexOf(p)]}))});
      if(a[i].rect.some((n,j)=>Math.abs(n-b[i].rect[j])>0.1)) diffs.push({index:i,class:a[i].class,type:'geometry',before:a[i].rect,after:b[i].rect});
    }
  }
  const hash = directory => crypto.createHash('sha256').update(fs.readFileSync(path.join(directory,page.name+'.png'))).digest('hex');
  return {name:page.name,nodes:b.length,differences:diffs.length,pixelIdentical:hash(beforeDirectory)===hash(afterDirectory),details:diffs};
});
const result={pages:pages.length,elements:pages.reduce((n,p)=>n+p.nodes,0),unchangedPages:pages.filter(p=>!p.differences).length,pixelIdenticalPages:pages.filter(p=>p.pixelIdentical).length,comparisons:pages};
fs.writeFileSync(path.join(outputDirectory,'visual-comparison.json'),JSON.stringify(result,null,2));
console.log(JSON.stringify({...result,comparisons:pages.filter(p=>p.differences).map(p=>({...p,details:p.details.slice(0,3)}))},null,2));
if(pages.some(p=>p.differences)) process.exitCode=1;
