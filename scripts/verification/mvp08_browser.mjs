// Reuse the accepted native Chrome driver, with strict local-only networking.
process.env.BONIRA_BROWSER_LOCAL_ONLY = '1';
await import('./mvp02_browser.mjs');
