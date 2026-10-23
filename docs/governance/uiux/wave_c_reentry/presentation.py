"""Exact presentation-only replacements; no hidden calculations or workflows."""
from pathlib import Path
ROOT = Path(__file__).resolve().parents[4]

def change(path, old, new):
    p = ROOT / path
    text = p.read_text(encoding="utf-8")
    if old not in text and new in text:
        return
    assert old in text, (path, old[:70])
    p.write_text(text.replace(old, new), encoding="utf-8")

time = "templates/timekeeping/workbench.html"
p = ROOT / time
s = p.read_text(encoding="utf-8")
setup = s[s.index('  {% if "time_calendars.manage"'):s.index('\n  {% if "attendance.capture"')]
s = s.replace(setup, "")
card = s[s.index('  <article class="erp-surface rounded-2xl p-5"><h2 class="font-black text-slate-950">تقویم و شیفت'):s.index('\n  <article class="erp-surface rounded-2xl p-5"><h2 class="font-black text-slate-950">حضور')]
s = s.replace(card, "")
s = s.replace('<div class="mt-5 flex flex-wrap gap-2">', '<section class="mt-5" aria-labelledby="daily-work"><h2 id="daily-work" class="font-bold">عملیات روزانه</h2><div class="mt-3 flex flex-wrap gap-2">', 1)
s = s.replace('</div>\n\n<section', '</div></section>\n\n<details class="erp-surface mt-5 rounded-xl p-5"><summary class="cursor-pointer font-bold">راه‌اندازی و تنظیمات تقویم و شیفت</summary><div class="mt-3 flex flex-wrap gap-2">' + setup + '</div>' + card + '</details>\n<section', 1)
p.write_text(s, encoding="utf-8")

pay = "templates/payroll/workbench.html"
change(pay, 'page_eyebrow="حریم خصوصی بالا" page_title="کارگاه حقوق و دستمزد" page_description="محاسبه غیرقانونی‌محور، نسخه‌پذیر و غیرارسال‌شونده؛ هیچ اثر حسابداری، خزانه، پرداخت یا هزینه پروژه ایجاد نمی‌شود."', 'page_eyebrow="حقوق و دستمزد" page_title="حقوق و دستمزد" page_description="دوره را انتخاب کنید، اجرا و نتایج را بررسی کنید و مراحل تأیید و صدور فیش را پیگیری کنید."')
change(pay, 'کارگاه حقوق و دستمزد |', 'حقوق و دستمزد |')
change(pay, 'class="erp-btn erp-btn--secondary" href="{% url \'payroll:period_create\' %}"', 'class="erp-btn {% if not periods %}erp-btn--primary{% else %}erp-btn--secondary{% endif %}" href="{% url \'payroll:period_create\' %}"')
change(pay, 'class="erp-btn erp-btn--primary" href="{% url \'payroll:run_create\' %}">اجرای جدید</a>', 'class="erp-btn erp-btn--secondary" href="{% url \'payroll:run_create\' %}">اجرای جدید</a>')
change(pay, '<div class="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900"><b>مرز حقوق:</b>', '<p class="mt-4 text-sm text-slate-600">برای اجرای حقوق، ابتدا دوره و پیکربندی پرداخت لازم است. ثبت ورودی، محاسبه، بررسی مستقل و قطعی‌سازی در صفحه هر اجرا انجام می‌شود.</p><details class="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900"><summary class="cursor-pointer font-bold">محدودیت محاسبه و ارسال</summary>')
change(pay, 'ارسال زنده ایجاد نمی‌شود.</div>', 'ارسال زنده ایجاد نمی‌شود.</details>')
for old, new in [("تاریخچه حساس", "سوابق بررسی حقوق"), ("صف استثنا", "موارد نیازمند بررسی"), ("نتایج حساس", "نتایج حقوق"), ("اجراهای قابل مشاهده", "اجراهای حقوق")]:
    change(pay, old, new)

run = "templates/payroll/run_detail.html"
change(run, 'page_description="ورودی، نسخه قاعده، مبنا، مقدار، نرخ، نتیجه و lineage برای بازتولید نگهداری می‌شوند."', 'page_description="نتایج کارکنان، وضعیت بررسی و اقدام بعدی این اجرا را پیگیری کنید."')
change(run, '<div class="erp-surface rounded-xl p-4"><span class="text-xs text-slate-500">هش محاسبه</span><b class="block truncate text-xs" dir="ltr">{{ run.calculation_digest|default:"—" }}</b></div>', '<details class="erp-surface rounded-xl p-4"><summary class="cursor-pointer text-sm font-bold">جزئیات بازتولید محاسبه</summary><span class="text-xs text-slate-500">هش محاسبه</span><b class="block break-all text-xs" dir="ltr">{{ run.calculation_digest|default:"—" }}</b></details>')
change(run, 'محاسبه Decimal', 'محاسبه حقوق')

stat = "templates/payroll/statutory_workbench.html"
change(stat, 'page_eyebrow="اطلاعات بسیار حساس" page_title="کارگاه مقرراتی مالیات و بیمه کارکنان" page_description="محاسبه، خروجی، correction lineage، شواهد export و تطبیق؛ بدون ارسال زنده یا اثر مالی پایین‌دست."', 'page_eyebrow="حقوق و دستمزد" page_title="مالیات و بیمه کارکنان" page_description="محاسبه، بررسی، آماده‌سازی خروجی و پیگیری وضعیت ثبت را با مقررات معتبر انجام دهید."')
change(stat, '<div class="mt-4 rounded-xl border border-blue-200 bg-blue-50 p-4 text-sm text-blue-900">خروجی ثبت‌شده در این بخش provider-neutral است. credential، اتصال، زمان‌بند، filing خودکار، AP، حسابداری، خزانه و هزینه پروژه وجود ندارد.</div>', '<details class="mt-4 rounded-xl border border-blue-200 bg-blue-50 p-4 text-sm text-blue-900"><summary class="cursor-pointer font-bold">محدودیت خروجی و ارسال</summary><p class="mt-2">محاسبه به نسخه مقرراتی معتبر نیاز دارد. خروجی به‌صورت خودکار ارسال نمی‌شود و هیچ تعهد مالی، سند حسابداری، پرداخت یا هزینه پروژه ایجاد نمی‌کند.</p></details>')
change(stat, 'حل انسانی', 'بررسی مسئول مربوط')

hand = "templates/payroll/financial_handoff_workbench.html"
change(hand, 'پیشنهادهای تغییرناپذیر؛ بدون شناسایی بدهی، سند حسابداری، پرداخت یا هزینه واقعی پروژه', 'تحویل نتایج حقوق به واحدهای مالی و پیگیری بررسی هر مقصد؛ ثبت تحویل به‌تنهایی اثر مالی ایجاد نمی‌کند')
change(hand, '<th class="p-2">lineage</th>', '<th class="p-2">نوع سابقه</th>')
change(hand, '<span class="block text-xs text-slate-500" dir="ltr">{{ item.predecessor_id }}</span>', '<details class="text-xs text-slate-500"><summary class="cursor-pointer">ردیابی سابقه پیشین</summary><span class="break-all" dir="ltr">{{ item.predecessor_id }}</span></details>')
