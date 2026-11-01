// Reuse the qualified Chrome probe, adding actual Tab/Shift+Tab input for this form.
import { readFile } from 'node:fs/promises';
const source = await readFile(new URL('./mvp02_browser.mjs', import.meta.url), 'utf8');
const marker = '      if(step.inspect) {';
if (!source.includes(marker)) throw new Error('Chrome probe keyboard extension seam changed');
const keyboard = `      if (step.key) {
        const modifiers = step.shift ? 8 : 0;
        await send('Input.dispatchKeyEvent', {type:'keyDown', key:step.key, code:step.key, windowsVirtualKeyCode:9, modifiers});
        await send('Input.dispatchKeyEvent', {type:'keyUp', key:step.key, code:step.key, windowsVirtualKeyCode:9, modifiers});
        await new Promise(done=>setTimeout(done,80));
      }
`;
const diagnostic = source.replace("await send('Runtime.enable');", "await send('Runtime.enable'); await send('Emulation.setFocusEmulationEnabled', {enabled:true});").replace(marker, keyboard + marker).replace(
  "if(!passed) throw new Error(scenario.name+': '+step.description);",
  `if(!passed) {
    await writeFile(join(outputDirectory, actor+'-failure.json'), JSON.stringify(await evaluate("({fields:[...document.querySelectorAll('.erp-form-field')].map(e=>({name:e.querySelector('[name]')?.name,rect:e.getBoundingClientRect().toJSON()})),project:document.querySelector('[name=project]')?.value,css:[...document.styleSheets].map(s=>s.href),grid:getComputedStyle(document.querySelector('.erp-form-grid')).gridTemplateColumns})"),null,2));
    const shot=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:true});
    await writeFile(join(outputDirectory,actor+'-failure.png'),Buffer.from(shot.data,'base64'));
    throw new Error(scenario.name+': '+step.description);
  }`
);
try {
  await import('data:text/javascript;base64,' + Buffer.from(diagnostic).toString('base64'));
} catch (error) {
  console.error(error.message);
  process.exitCode = 1;
}
