"""Bounded Wave C presentation repairs; retain exact effective entry sources."""
import json
from pathlib import Path

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[3]
changes={
 'templates/projects/controls.html':[
 ('شواهد محدود کنترل پروژه','بودجه و هزینه پروژه'),
 ('فقط بودجه پذیرفته‌شده و هزینه تأییدشده/ثبت‌شده کدگذاری‌شده نمایش یا صادر می‌شود.','بودجه پذیرفته‌شده و هزینه‌های تأییدشده یا ثبت‌شده را بررسی کنید.'),
 ('<span class="rounded-full bg-amber-50 px-3 py-1 text-xs font-medium text-amber-800">مشاهده‌ای؛ بدون هشدار، توقف یا رزرو</span>','<details class="text-xs text-slate-500"><summary class="cursor-pointer">درباره اطلاعات این بخش</summary><p class="mt-2">این گزارش برای مشاهده است و هشدار، توقف یا رزرو ایجاد نمی‌کند.</p></details>'),
 ('تطبیق محدود چندمنبعی','تطبیق منابع هزینه'),
 ('برای مشاهدهٔ این شواهد، مجوز اختصاصی مقایسه، انحرافات بودجه‌ای، خروجی یا تطبیق چندمنبعی لازم است.','در صورت نیاز به گزارش مقایسه، انحرافات یا تطبیق هزینه، دسترسی مربوط را از مدیر شرکت درخواست کنید.'),
 ],
 'templates/contracts/commercial_review.html':[
 ('مرور مشورتی P6','مرور تجاری قرارداد'),
 ('فقط شواهد و نسخه‌های موجود؛ بدون اثر خودکار بر قرارداد، برنامه یا مالی','رویدادهای قرارداد، مبالغ و تغییرات مدت را بر اساس سوابق موجود مقایسه کنید.'),
 ('تبار شواهد قراردادی','مدارک و سوابق مرتبط'),
 ('<span class="text-xs text-slate-500" dir="ltr">{{ item.source_type }} / {{ item.source_id }}</span>','<details class="mt-2 text-xs text-slate-500"><summary class="cursor-pointer">ردیابی مدرک</summary><p class="mt-2" dir="ltr">{{ item.source_type }} / {{ item.source_id }}</p></details>'),
 ('استثناهای مشورتی','موارد نیازمند بررسی'),
 ],
 'templates/timekeeping/workbench.html':[
 ('حضور واقعیت حضور است؛ کارکرد تخصیص مصوب زمان. تاریخچه قطعی فقط با اصلاح مستدل حفظ می‌شود.','حضور کارکنان، درخواست‌ها و کارکرد دوره را بررسی و پیگیری کنید.'),
 ('صف استثنا و حضور','حضور و موارد نیازمند بررسی'),
 ('<th class="p-2">دامنه</th>','<th class="p-2">پروژه و کارگاه</th>'),
 ('<span dir="ltr" class="block text-xs text-amber-700">{{ item.exception_code }}</span>','<details class="text-xs text-amber-700"><summary class="cursor-pointer">جزئیات مورد نیازمند بررسی</summary><span dir="ltr">{{ item.exception_code }}</span></details>'),
 ('رکوردی در دامنه دسترسی نیست.','سابقه حضوری برای نمایش وجود ندارد.'),
 ('پیش‌نمایش فقط دقیقه‌ها را نگهداری می‌کند؛ نرخ، حقوق، هزینه پروژه، تعهد یا سند مالی ایجاد نمی‌شود.','زمان صرف‌شده برای هر پروژه و فعالیت را در سوابق کارکرد بررسی کنید.'),
 ('کارکردی در دامنه دسترسی نیست.','سابقه کارکردی برای نمایش وجود ندارد.'),
 ],
 'templates/documents/list.html':[
 ('نسخه‌های immutable با دسترسی مبتنی بر context','اسناد نسخه‌بندی‌شده با دسترسی بر اساس شرکت و پروژه'),
 ],
 'templates/procurement/portal_accept.html':[
 ('<main class="mx-auto max-w-lg"','<section class="mx-auto max-w-lg"'),
 ('</section></main>','</section></section>'),
 ],
 'templates/procurement/rfq_buyer_workspace.html':[
 ('ثبت مستند در منبع تدارکات، با مجوز مرحله و تفکیک وظایف','پیشنهادهای دریافتی، مقایسه تأمین‌کنندگان و سوابق انتخاب را بررسی کنید.'),
 ('پیش‌نیازها و تفکیک وظایف','راهنمای بررسی و انتخاب'),
 ('ثبت پیشنهاد از دعوت‌نامه نسخه مؤثر استعلام انجام می‌شود.','پیشنهاد را برای دعوت‌نامه جاری همین استعلام ثبت کنید.'),
 ('گشایش پس از بستن ثبتی، زمان مجاز و احراز سلامت شواهد انجام می‌شود؛ درخواست‌کننده نمی‌تواند تأییدکننده باشد.','پیشنهادها پس از بسته‌شدن استعلام، در زمان تعیین‌شده و با بررسی مدارک باز می‌شوند. درخواست‌کننده و تأییدکننده باید دو نفر متفاوت باشند.'),
 ('پذیرش و ورودی‌های تجاری به دسترسی فعال همان نسخه نیاز دارند.','برای بررسی پیشنهاد، باید به همان نسخه دسترسی داشته باشید.'),
 ('مقایسه به دامنه تجاری حاکم و پذیرش معتبر نیاز دارد؛ ارزیابی به انتصاب فعال و تعیین تکلیف تعارض وابسته است.','فقط پیشنهادهای پذیرفته‌شده را در گروه مقایسه مربوط بررسی کنید. ارزیاب باید تعیین شده باشد و تعارض منافع او بررسی شده باشد.'),
 ('نهایی‌سازی تابع سیاست فعال تفکیک وظایف شرکت است؛ نبود سیاست یا منبع، عملیات را متوقف می‌کند.','برای نهایی‌سازی، مدارک لازم و تأییدکنندگان تعیین‌شده شرکت باید آماده باشند.'),
 ('انتخاب، تصمیم مستند تدارکات است و قرارداد یا سند مالی ایجاد نمی‌کند.','انتخاب تأمین‌کننده در این صفحه ثبت می‌شود؛ ایجاد قرارداد و سند مالی مراحل جداگانه‌اند.'),
 ],
 'apps/accounting/templates/accounting/statement_list.html':[
 ('پیش‌نمایش {{ form.cleaned_data.kind }}','پیش‌نمایش {% for value, label in form.fields.kind.choices %}{% if value == preview.kind %}{{ label }}{% endif %}{% endfor %}'),
 ('{{ line.account_type }}','{% for value, label in account_type_choices %}{% if value == line.account_type %}{{ label }}{% endif %}{% endfor %}'),
 ],
 'apps/accounting/views.py':[
 ('    Account,\n','    Account,\n    AccountType,\n'),
 ('            "preview": preview,\n','            "preview": preview,\n            "account_type_choices": AccountType.choices,\n'),
 ],
 'apps/accounting/templates/accounting/statement_detail.html':[
 ('<div class="sm:col-span-3"><dt class="text-xs text-slate-500">هش‌های دامنه / ورودی / نتیجه</dt><dd class="mt-1 break-all font-mono text-xs" dir="ltr">{{ run.scope_hash }}<br>{{ run.input_hash }}<br>{{ run.result_hash }}</dd></div>','</dl><details class="mt-4 rounded-lg border border-slate-200 p-3"><summary class="cursor-pointer text-sm font-medium">ردیابی و ممیزی</summary><dl class="mt-3"><dt class="text-xs text-slate-500">هش‌های دامنه / ورودی / نتیجه</dt><dd class="mt-1 break-all font-mono text-xs" dir="ltr">{{ run.scope_hash }}<br>{{ run.input_hash }}<br>{{ run.result_hash }}</dd>'),
 ('</dd></dl></section>','</dd></dl></details></section>'),
 ],
 'apps/subledgers/templates/subledgers/workbench.html':[
 ('<p class="text-slate-600">گزارش سنی دقیق در تاریخ مبنا، بدون بازه‌بندی. شناسایی دریافتنی و پرداختنی از اسناد مبدأ، ثبت سند حسابداری و تأیید و برگشت حذف حسابداری مانده هنوز فعال نشده‌اند.</p>','<p class="text-slate-600">مانده اقلام، تخصیص تراکنش‌های قطعی خزانه و موارد نیازمند بررسی را پیگیری کنید.</p><details class="mt-3 text-sm text-slate-500"><summary class="cursor-pointer">درباره گزارش‌ها و قابلیت‌های فعلی</summary><p class="mt-2">گزارش سنی دقیق در تاریخ مبنا، بدون بازه‌بندی. شناسایی دریافتنی و پرداختنی از اسناد مبدأ، ثبت سند حسابداری و تأیید و برگشت حذف حسابداری مانده هنوز فعال نشده‌اند.</p></details>'),
 ],
 'templates/inventory/custody_workbench.html':[
 ('رزرو، شمارش، انتقال، رهگیری و تطبیق؛ بدون ارزش‌گذاری یا ثبت مالی','رزروها، شمارش انبار، انتقال کالا و موعد انقضای اقلام را پیگیری کنید.'),
 ('مغایرت تخصیص','مغایرت در تخصیص موجودی'),('مواضع بدون تخصیص','موجودی تخصیص‌نیافته'),('تخصیص میراثی نامشخص','تخصیص‌های قدیمی نیازمند بررسی'),
 ('<p class="mt-4 text-xs text-slate-500">این کارتابل فقط مقدار و امانت را کنترل می‌کند و هیچ ارزش‌گذاری، سند حسابداری، هزینه واقعی پروژه یا اثر دارایی ثابت ایجاد نمی‌کند.</p>','<details class="mt-4 text-xs text-slate-500"><summary class="cursor-pointer">درباره کنترل مقدار و امانت</summary><p class="mt-2">این کارتابل فقط مقدار و امانت را کنترل می‌کند و هیچ ارزش‌گذاری، سند حسابداری، هزینه واقعی پروژه یا اثر دارایی ثابت ایجاد نمی‌کند.</p></details>'),
 ],
 'apps/inventory/p8_views.py':[
 ('from apps.organizations.decorators import (','from apps.organizations.authorization import has_business_permission\nfrom apps.organizations.decorators import ('),
 ('        "reconciliation": valuation_reconciliation(organization=request.organization, actor=request.user),','        "reconciliation": (\n            valuation_reconciliation(organization=request.organization, actor=request.user)\n            if has_business_permission(\n                user=request.user,\n                organization=request.organization,\n                permission=BusinessPermissionCode.INVENTORY_VALUATION_RECONCILE,\n            )\n            else None\n        ),'),
 ],
 'templates/inventory/valuation_workbench.html':[
 ('<section class="erp-surface mt-6 rounded-xl p-4"><h2 class="font-bold">نتایج تطبیق ارزش‌گذاری</h2>','{% if reconciliation is not None %}<section class="erp-surface mt-6 rounded-xl p-4"><h2 class="font-bold">نتایج تطبیق ارزش‌گذاری</h2>'),
 ('{{ items|length }}</b></div>{% endfor %}</div></section>','{{ items|length }}</b></div>{% endfor %}</div></section>{% endif %}'),
 ],
}

if __name__=='__main__':
    assert not (OUT/'TOUCH_SET.json').exists()
    entry=OUT/'entry_sources'
    entry.mkdir()
    for name in changes:
        target=entry/name
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes((ROOT/name).read_bytes())
    (OUT/'TOUCH_SET.json').write_text(json.dumps(dict(product=list(changes),reason='F009/F011/F014/F023/F092/F093 presentation; F129 portal nested landmark; F130 optional protected reconciliation prevents authorized valuation view',migration='NO',services_changed=False,permission_definitions_changed=False),indent=2)+'\n')
    for name,replacements in changes.items():
        p=ROOT/name
        text=p.read_text(encoding='utf-8')
        for old,new in replacements:
            assert text.count(old)==1,(name,old,text.count(old))
            text=text.replace(old,new,1)
        p.write_text(text,encoding='utf-8',newline='\n')
    print('Bounded remediation:',len(changes),'files; exact entry copies retained')
