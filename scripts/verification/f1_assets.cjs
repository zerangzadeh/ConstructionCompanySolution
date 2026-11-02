// Verify utilities actually rendered by Django/JS exist in the production CSS.
const fs = require('node:fs');
const crypto = require('node:crypto');
const postcss = require('postcss');
const selectorParser = require('postcss-selector-parser');
const resolveConfig = require('tailwindcss/resolveConfig');
const {createContext} = require('tailwindcss/lib/lib/setupContextUtils');
const {generateRules} = require('tailwindcss/lib/lib/generateRules');
const fg = require('fast-glob');
const config = require('../../tailwind.config.cjs');
const css = fs.readFileSync('apps/accounts/static/css/tailwind.css', 'utf8');
const classes = new Set();
postcss.parse(css).walkRules(rule => {
  selectorParser(selectors => selectors.walkClasses(node => classes.add(node.value))).processSync(rule.selector);
});
const evidencePath = process.argv[2] || 'output/f1/offline/results.json';
const evidence = JSON.parse(fs.readFileSync(evidencePath, 'utf8'));
const rendered = new Set(evidence.results.flatMap(page => page.state.classes));
const ctx = createContext(resolveConfig(config));
const required = [...rendered].filter(candidate => [...generateRules(new Set([candidate]), ctx)].length);
const missing = required.filter(candidate => !classes.has(candidate));
const files = fg.sync(config.content.files);
const forbidden = files.filter(path => /\/(?:output|evidence|migrations|vendor|tests)\//.test(path) || /\/test_[^/]+\.py$/.test(path));
const version = require('tailwindcss/package.json').version;
const result = {
  version, cssBytes:Buffer.byteLength(css), sha256:crypto.createHash('sha256').update(css).digest('hex'),
  content:{total:files.length,html:files.filter(p=>p.endsWith('.html')).length,js:files.filter(p=>p.endsWith('.js')).length,python:files.filter(p=>p.endsWith('.py')).length},
  renderedClasses:rendered.size,requiredTailwindClasses:required.length,compiledClasses:classes.size,missing,forbidden,
  safelist:config.safelist,
};
console.log(JSON.stringify(result,null,2));
if (version !== '3.4.17' || missing.length || forbidden.length) process.exitCode = 1;
