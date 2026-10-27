// Disposable PostgreSQL test-server UI qualification; bundled Playwright only.
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require(path.join(process.env.BONIRA_QA_MODULES, 'playwright'));

(async () => {
  const base = process.env.BONIRA_QA_URL;
  const output = process.env.BONIRA_QA_OUTPUT;
  if (!/^http:\/\/(localhost|127\.0\.0\.1):\d+$/.test(base)) throw new Error('Local test server required');
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({ headless: true, executablePath: process.env.BONIRA_QA_BROWSER || undefined });
  const context = await browser.newContext();
  const page = await context.newPage();
  const captures = [];
  const setActor = async (name) => {
    await context.clearCookies();
    await context.addCookies([{ name: 'sessionid', value: process.env[name], url: base }]);
  };
  const capture = async (state) => {
    for (const width of [1440, 390]) {
      await page.setViewportSize({ width, height: 900 });
      await page.evaluate(() => document.fonts.ready);
      const result = await page.evaluate(() => ({
        rtl: document.documentElement.dir === 'rtl',
        overflow: document.documentElement.scrollWidth > window.innerWidth + 1,
      }));
      if (!result.rtl || result.overflow) throw new Error(`Layout check failed: ${state}/${width}`);
      const filename = `${state}-${width}.png`;
      await page.screenshot({ path: path.join(output, filename), fullPage: true });
      captures.push({ state, width, filename, ...result });
    }
  };
  try {
    await setActor('BONIRA_QA_MAKER');
    await page.goto(`${base}/accounting/year-end/`);
    await page.getByRole('heading', { name: 'بستن سال و انتقال مانده‌ها', exact: true }).waitFor();
    await capture('list');
    await page.getByRole('link', { name: 'تنظیم حساب نتیجه سال و سود انباشته', exact: true }).click();
    await page.getByLabel('حساب نتیجه سال', { exact: false }).waitFor();
    await capture('configuration');
    await page.goto(`${base}/accounting/year-end/`);
    await page.getByLabel('سال مالی مبدأ', { exact: false }).selectOption(process.env.BONIRA_QA_SOURCE);
    await page.getByLabel('سال مالی بعد', { exact: false }).selectOption(process.env.BONIRA_QA_TARGET);
    await page.getByLabel('دلیل و یادداشت بررسی', { exact: false }).fill('بررسی نهایی سال و انتقال مانده‌ها');
    await page.getByRole('button', { name: 'آغاز بستن و ارسال برای تأیید مستقل', exact: true }).click();
    await page.getByText('در انتظار تأیید بستن', { exact: true }).waitFor();
    await capture('prepared');
    await setActor('BONIRA_QA_CHECKER');
    await page.reload();
    const approveForm = page.locator('form').filter({ has: page.getByRole('button', { name: 'تأیید بستن سال', exact: true }) });
    await approveForm.getByLabel('دلیل', { exact: false }).fill('تأیید مستقل مانده‌ها و نتیجه سال');
    await approveForm.getByRole('button', { name: 'تأیید بستن سال', exact: true }).click();
    await page.getByText('سال بسته؛ در انتظار افتتاحیه', { exact: true }).waitFor();
    await capture('closed');
    await page.getByLabel('دلیل', { exact: false }).first().fill('تأیید مستقل افتتاحیه حاصل از اختتامیه');
    await page.getByRole('button', { name: 'ایجاد و پذیرش افتتاحیه', exact: true }).click();
    await page.getByText('اختتامیه و افتتاحیه برابر است', { exact: true }).waitFor();
    await capture('rolled-forward');
    await setActor('BONIRA_QA_REOPENER');
    await page.reload();
    await page.getByLabel('درخواست‌کننده مستقل بازگشایی', { exact: false }).selectOption(process.env.BONIRA_QA_REQUESTER);
    await page.getByLabel('دلیل', { exact: false }).fill('اصلاح مجاز با برگشت کامل اسناد و تطبیق مستقل');
    await page.getByRole('button', { name: 'برگشت و بازگشایی', exact: true }).click();
    await page.getByText('برگشت و بازگشایی شده', { exact: true }).waitFor();
    await capture('reopened');
    fs.writeFileSync(path.join(output, 'browser-qualification.json'), JSON.stringify({ status: 'PASS', captures }, null, 2));
    process.stdout.write(JSON.stringify({ status: 'PASS', screenshots: captures.length }));
  } finally {
    await browser.close();
  }
})().catch((error) => { process.stderr.write(String(error)); process.exitCode = 1; });
