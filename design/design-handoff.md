# سیستم طراحی و راهنمای تحویل فنی (Design Handoff) سامانه جامع ERP عمرانی
**پروژه:** عمران‌سازان (Civil Slate Enterprise)  
**معماری هدف توسعه:** Django 5.x + Django Templates + Tailwind CSS (با تعاملات اختیاری HTMX، فقط در صورت پشتیبانی معماری موجود)  
**جهت و زبان پایه:** `dir="rtl"` / `lang="fa-IR"` با استثنائات ایزوله `dir="ltr"` برای داده‌های فنی و مبالغ.

---

## Source of Truth

These design documents define visual presentation only.

این سامانه دیگر MVP نیست و این راهنما برای رابط یک محصول کامل، حرفه‌ای و قابل
بهره‌برداری تدوین شده است. گسترش پوشش صفحات مرحله‌ای و تابع `ROADMAP.md` است و
این هدف کیفی مجوز ایجاد رفتار یا قابلیت بک‌اندِ تصویب‌نشده نیست.

The existing ERP application remains authoritative for:
- models
- database schema
- URLs
- permissions
- validation
- tenant isolation
- workflows
- services
- business rules

When design documentation conflicts with existing application behavior,
preserve the existing application behavior.

---

## ۱. مبانی معماری و هویت بصری (Architecture & Foundations)

این بسته تحویل دیزاین (Design Handoff) مستقیماً برای استفاده توسط تیم توسعه و ابزارهای کدنویسی هوشمند (Codex) بر مبنای ساختار ماژولار قالب‌های جنگو و کلاس‌های کاربردی Tailwind CSS آماده شده است. از هرگونه پیچیدگی کتابخانه‌های SPA (مانند React/Vue) اجتناب شده و رندر صفحات بر عهده سرور جنگو است.

### ساختار کلی چیدمان صفحه (Base Shell Layout)
* **سایدبار راست (Right Fixed Sidebar):** عرض ثابت `260px` (`w-[260px]`)، موقعیت فیکس `fixed right-0 top-0 h-full`، لایه `z-50`. پس‌زمینه سالید تم تیره نوی/اسلیت (`#0F172A` یا `bg-slate-900 / bg-inverse-surface`).
* **هدر ناوبری بالایی (Top Header):** ارتفاع ثابت `60px` (`h-[60px]`)، موقعیت `fixed top-0 right-[260px] left-0`، لایه `z-40`، پس‌زمینه سفید خالص با بوردر تفکیک‌کننده Slate-200.
* **فضای محتوای اصلی (Main Content Wrapper):** دارای کلاس مارجین/پدینگ راست `pr-[260px]`، با افست بالایی `pt-[60px]`، و پدینگ بدنه `p-6` (`p-space-lg`). پس‌زمینه کانواس کاری خنثی و تمیز `#F8FAFC` (`bg-slate-50`).

---

## ۲. توکن‌های جامع طراحی (Design Tokens & Tailwind Config)

### الف. پالت رنگ‌ها (Color Palette & Semantic Tokens)
```javascript
// tailwind.config.js - بخش رنگ‌ها
module.exports = {
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // پس‌زمینه‌ها و سطوح (Surfaces & Layout)
        surface: {
          DEFAULT: '#F8FAFC', // Slate-50: پس‌زمینه اصلی بدنه و صفحات
          white: '#FFFFFF',   // کارت‌ها و پنل‌های داده
          subtle: '#F1F5F9',  // Slate-100: پس‌زمینه المان‌های درونی فرم‌ها و تب‌ها
          muted: '#E2E8F0',   // Slate-200: حاشیه‌ها و جداکننده‌ها
        },
        // سایدبار تیره سازمانی (Dark Navy Sidebar)
        sidebar: {
          bg: '#0F172A',      // Slate-900: رنگ اصلی سایدبار
          border: '#1E293B',  // Slate-800: تفکیک‌کننده‌ها
          hover: '#1E293B',
          active: '#1D4ED8',  // برند فعال در سایدبار
          text: '#94A3B8',    // Slate-400: منوهای غیرفعال
          'text-active': '#FFFFFF',
        },
        // رنگ برند اصلی سازمانی (Primary Brand - Cobalt Blue)
        primary: {
          DEFAULT: '#1D4ED8', // Blue-700
          hover: '#1E40AF',   // Blue-800
          light: '#EFF6FF',   // Blue-50 (پس‌زمینه آیتم فعال و بج‌ها)
          border: '#BFDBFE',  // Blue-200
        },
        // وضعیت‌های معنایی (Semantic Status Colors)
        status: {
          success: {
            text: '#15803D',    // Green-700
            bg: '#F0FDF4',      // Green-50
            border: '#BBF7D0',  // Green-200
          },
          info: {
            text: '#1D4ED8',    // Blue-700
            bg: '#EFF6FF',      // Blue-50
            border: '#BFDBFE',  // Blue-200
          },
          warning: {
            text: '#B45309',    // Amber-700
            bg: '#FFFBEB',      // Amber-50
            border: '#FDE68A',  // Amber-200
          },
          danger: {
            text: '#B91C1C',    // Red-700
            bg: '#FEF2F2',      // Red-50
            border: '#FECACA',  // Red-200
          },
          neutral: {
            text: '#475569',    // Slate-600
            bg: '#F1F5F9',      // Slate-100
            border: '#CBD5E1',  // Slate-300
          },
        },
        // خاکستری‌های تایپوگرافی (Text Shades)
        content: {
          primary: '#0F172A',   // Slate-900: تیترها و مقادیر مهم
          secondary: '#334155', // Slate-700: متن‌های پیش‌فرض
          muted: '#64748B',     // Slate-500: متاداده و عناوین ستون‌ها
          subtle: '#94A3B8',    // Slate-400: پلیس‌هولدرها و ایکون‌های غیرفعال
        }
      }
    }
  }
}
```

### ب. تایپوگرافی و مقیاس فونت (Typography Scale)
* **قلم اصلی فارسی:** `Vazirmatn, system-ui, -apple-system, sans-serif`
* **قلم کدهای فنی و اعداد LTR:** `JetBrains Mono, SFMono-Regular, Consolas, monospace`

| سطح | اندازه | Line-height | وزن (Weight) | موارد استفاده |
| :--- | :--- | :--- | :--- | :--- |
| **Page Title** | 24px (`text-2xl`) | 32px (`leading-8`) | Bold (700) | عنوان اصلی بالای هر صفحه |
| **Section Header** | 16px (`text-base`) | 24px (`leading-6`) | SemiBold (600) | هدر کارت‌ها، جداول و سکشن‌ها |
| **Subsection / Label** | 14px (`text-sm`) | 20px (`leading-5`) | Medium (500) / SemiBold | لیبل فیلدها، سرستون‌های جدول، دکمه‌ها |
| **Body Default** | 13px (`text-[13px]`) | 20px | Regular (400) | داده‌های داخل جدول، توضیحات و پاراگراف‌ها |
| **Caption & Meta** | 12px (`text-xs`) | 16px | Regular / Medium | متن‌های کمکی زیر اینپوت‌ها، برچسب‌ها |
| **Technical Code** | 12px/13px | - | Medium (500) + LTR | شناسه‌ها، مبالغ، مقادیر اوزان، شماره پلاک |

### ج. فواصل، شعاع گوشه‌ها و سایه‌ها (Spacing, Radii & Shadows)
* **شعاع گوشه‌ها (Border Radius):**
  * کارت‌های بزرگ و کانتینرها: `rounded-xl` (12px)
  * دکمه‌ها، ورودی‌های فرم و فیلترها: `rounded-lg` (8px)
  * برچسب‌های وضعیت (Badges & Pills): `rounded-full` یا `rounded-md` (6px)
  * باکس آیکون‌های درون کارت: `rounded-lg` (8px)
* **سایه‌ها (Restrained Enterprise Shadows):**
  * سایه استاندارد کارت‌ها: `shadow-sm` (`box-shadow: 0 1px 2px 0 rgb(0 0 0 / 0.05)`)
  * منوهای بازشونده و دراپ‌داون‌ها: `shadow-md` یا `shadow-lg`
* **فاصله‌گذاری استاندارد (Spacing System):**
  * گرید اصلی کارت‌ها و فرم‌ها: `gap-4` (16px) تا `gap-6` (24px).
  * پدینگ داخل کارت‌ها: `p-4` تا `p-6`.
  * حاشیه‌های تفکیک‌کننده عمودی: `border-slate-200`.

---

## ۳. قوانین حیاتی راست‌چین و چپ‌چین (RTL / LTR Rules)

۱. **جهت کلی بدنه:**  
   تگ اصلی در جنگو باید با `<html dir="rtl" lang="fa-IR">` رندر شود.
۲. **قانون ایزوله‌سازی مقادیر فنی (Strict LTR Isolation):**  
   تمام اقلام داده‌ای زیر **باید حتماً** دارای ویژگی `dir="ltr"` و در تگ‌های تک خطی مانند `<span>`، `<code>` یا کلاس‌های فونت مونو باشند:
   - کدهای ساختار شکست کار (WBS): مثل `WBS-02.04.11`
   - شناسه‌های سیستمی و یکتای اسناد: مثل `PRJ-1403-01`, `GRN-1403-1104`, `NCR-1403-084`, `EMP-1403-042`, `DPR-1403-0241`
   - مبالغ ریالی و ارزی با جداکننده کاما: مثل `18,400,000,000 IRR` یا `285,000 ریال`
   - مقادیر عددی اوزان و متراژ به همراه واحد: مثل `24,250 KG`, `420.0 m³`, `22,450 kg`
   - شماره بارنامه‌ها، پلاک‌های ماشین و شناسه ملی: `BL-894102-IR`
   - تاریخ‌های میلادی و ساعت‌های تردد گیت: `07:12:00`, `2024-11-15`
   - شماره تلفن‌ها و ایمیل‌ها.
۳. **آیکون‌های جهت‌دار (Directional Icons):**  
   آیکون‌هایی مانند پیکان‌های رفت‌وبرگشت یا پیجینیشن باید متناسب با جهت راست‌چین تنظیم شوند (پیکان قبلی به سمت راست و بعدی به سمت چپ اشاره می‌کند).

---

## ۴. مشخصات فنی کامپوننت‌های رابط کاربری (Component Specifications)

### ۱. دکمه‌ها (Buttons)
* **دکمه اقدام اصلی (Primary Action):**
  ```html
  <button type="submit" class="inline-flex items-center justify-center gap-1.5 h-9 px-4 rounded-lg bg-blue-700 hover:bg-blue-800 active:bg-blue-900 text-white text-sm font-semibold transition-colors shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500/20">
    <span class="material-symbols-outlined text-[18px]">add_circle</span>
    <span>ثبت فعالیت جدید</span>
    <kbd class="font-mono text-[10px] bg-blue-600 px-1 py-0.5 rounded text-blue-100" dir="ltr">F2</kbd>
  </button>
  ```
* **دکمه ثانویه / خنثی (Secondary / Outline Button):**
  ```html
  <button type="button" class="inline-flex items-center justify-center gap-1.5 h-9 px-3.5 rounded-lg bg-white border border-slate-300 hover:bg-slate-50 text-slate-700 text-sm font-medium transition-colors shadow-xs">
    <span class="material-symbols-outlined text-[18px] text-slate-500">print</span>
    <span>چاپ فرم</span>
  </button>
  ```

### ۲. کارت‌های شاخص عملکرد (KPI Summary Cards)
ساختار یکپارچه در گرید ۴ ستونه (`grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4`):
```html
<div class="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex flex-col justify-between">
  <div class="flex items-center justify-between">
    <span class="text-slate-500 text-xs font-medium">نیروی انسانی کل</span>
    <div class="w-8 h-8 rounded-lg bg-blue-50 text-blue-700 flex items-center justify-center">
      <span class="material-symbols-outlined text-[18px]">groups</span>
    </div>
  </div>
  <div class="flex items-baseline gap-2 my-2.5">
    <span class="text-2xl font-extrabold text-slate-900 font-mono" dir="ltr">214</span>
    <span class="text-xs text-slate-500">نفر در کارگاه</span>
  </div>
  <div class="flex items-center justify-between pt-2 border-t border-slate-100 text-xs text-slate-600">
    <span>دفتر فنی: <strong class="text-blue-700 font-mono">۳۴</strong></span>
    <span>اکیپ پیمانکاران: <strong class="text-slate-800 font-mono">۱۸۰</strong></span>
  </div>
</div>
```

### ۳. جدول داده‌های سازمانی با تراکم بالا (High-Density Data Table)
* ارتفاع ردیف ۴۰ تا ۴۸ پیکسل، هاور نامحسوس `hover:bg-slate-50/80`، با خطوط جداکننده افقی `border-b border-slate-200`.
```html
<div class="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
  <!-- هدر ابزار و فیلترهای سریع جدول -->
  <div class="flex flex-wrap items-center justify-between p-3.5 bg-slate-50/70 border-b border-slate-200 gap-2">
    <h3 class="text-sm font-bold text-slate-900">ریز جبهه‌های کاری فعال در روز</h3>
    <div class="flex items-center gap-2">
      <input type="text" placeholder="جستجو بر اساس کد WBS..." class="h-8 pr-7 pl-3 rounded-lg bg-white border border-slate-300 text-xs text-slate-800 placeholder:text-slate-400 focus:outline-none focus:border-blue-600 w-56">
    </div>
  </div>

  <div class="overflow-x-auto w-full">
    <table class="w-full text-right border-collapse text-xs">
      <thead>
        <tr class="bg-slate-50 text-slate-600 font-semibold border-b border-slate-200">
          <th class="py-2.5 px-3 text-center w-12">ردیف</th>
          <th class="py-2.5 px-3 text-left w-36 font-mono">کد WBS</th>
          <th class="py-2.5 px-3 w-48">جبهه کاری</th>
          <th class="py-2.5 px-3">شرح عملیات</th>
          <th class="py-2.5 px-3 w-40">پیمانکار / اکیپ</th>
          <th class="py-2.5 px-3 text-left w-28 font-mono">مقدار</th>
          <th class="py-2.5 px-3 text-center w-28">وضعیت تایید</th>
          <th class="py-2.5 px-3 text-center w-16">عملیات</th>
        </tr>
      </thead>
      <tbody class="divide-y divide-slate-100 text-slate-800">
        <tr class="hover:bg-slate-50 transition-colors">
          <td class="py-2.5 px-3 text-center text-slate-400 font-mono">01</td>
          <td class="py-2.5 px-3 text-left font-mono font-bold text-blue-700" dir="ltr">WBS-02.04.11</td>
          <td class="py-2.5 px-3 font-medium">سقف طبقه +5 (زون 2)</td>
          <td class="py-2.5 px-3 text-slate-600">آرماتوربندی تیرهای اصلی با میلگرد آجدار A3</td>
          <td class="py-2.5 px-3">اکیپ استاد حسینی</td>
          <td class="py-2.5 px-3 text-left font-mono font-semibold" dir="ltr">14,200 kg</td>
          <td class="py-2.5 px-3 text-center">
            <span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
              <span class="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
              تایید شده
            </span>
          </td>
          <td class="py-2.5 px-3 text-center">
            <button class="w-7 h-7 rounded hover:bg-slate-100 text-slate-600 inline-flex items-center justify-center">
              <span class="material-symbols-outlined text-[16px]">more_vert</span>
            </button>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</div>
```

### ۴. برچسب‌های وضعیت و نشانگرها (Status Badges)
* **تایید شده / موفق (Approved / Success):**
  `bg-emerald-50 text-emerald-700 border border-emerald-200 px-2 py-0.5 rounded-full text-[11px] font-semibold`
* **در جریان / در حال بررسی (In Progress / Info):**
  `bg-blue-50 text-blue-700 border border-blue-200 px-2 py-0.5 rounded-full text-[11px] font-semibold`
* **هشدار / معلق (Warning / Pending):**
  `bg-amber-50 text-amber-700 border border-amber-200 px-2 py-0.5 rounded-full text-[11px] font-semibold`
* **مردود / بحرانی / خطای HSE (Critical / Rejection):**
  `bg-rose-50 text-rose-700 border border-rose-200 px-2 py-0.5 rounded-full text-[11px] font-semibold`
* **خنثی / پیش‌نویس (Neutral / Draft):**
  `bg-slate-100 text-slate-600 border border-slate-200 px-2 py-0.5 rounded-full text-[11px] font-semibold`

### ۵. فرم‌ها و فیلدهای ورودی (Forms & Inputs)
```html
<div class="space-y-1">
  <label class="block text-xs font-semibold text-slate-700">شماره حواله خروج کارگاهی (Gate Pass)</label>
  <div class="relative">
    <input type="text" name="pass_code" value="GP-1403-0891" dir="ltr"
           class="w-full h-9 px-3 rounded-lg border border-slate-300 bg-white font-mono text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-600/20 focus:border-blue-600">
  </div>
  <p class="text-[11px] text-slate-500">شناسه به صورت سیستمی تولید می‌شود.</p>
</div>
```

### ۶. تب‌های فیلتر و سوییچ وضعیت (Filter Tabs)
```html
<div class="flex items-center gap-1 overflow-x-auto p-1 bg-white border border-slate-200 rounded-xl shadow-xs">
  <button class="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-blue-700 text-white text-xs font-semibold shadow-xs">
    <span>همه پرونده‌ها</span>
    <span class="bg-blue-800 text-blue-100 font-mono text-[10px] px-1.5 py-0.5 rounded-full">۳۸</span>
  </button>
  <button class="flex items-center gap-2 px-3 py-1.5 rounded-lg text-slate-600 hover:bg-slate-100 text-xs font-medium transition-colors">
    <span>مردود قطعی</span>
    <span class="bg-slate-100 text-slate-600 font-mono text-[10px] px-1.5 py-0.5 rounded-full">۴</span>
  </button>
  <button class="flex items-center gap-2 px-3 py-1.5 rounded-lg text-slate-600 hover:bg-slate-100 text-xs font-medium transition-colors">
    <span>قرنطینه آزمایشگاه</span>
    <span class="bg-slate-100 text-slate-600 font-mono text-[10px] px-1.5 py-0.5 rounded-full">۶</span>
  </button>
</div>
```

### ۷. جعبه‌های هشدار و پیام‌های عملیاتی (Alerts & Notice Boxes)
```html
<div class="p-3.5 rounded-xl bg-amber-50 border border-amber-200 flex items-start gap-3">
  <span class="material-symbols-outlined text-amber-700 text-[20px] shrink-0 mt-0.5">warning</span>
  <div class="flex flex-col text-xs">
    <span class="font-bold text-amber-800">تاخیر ترافیکی و لجستیک در تحویل تراک‌میکسرها</span>
    <span class="text-amber-700/90 mt-0.5">به علت انسداد موقت بزرگراه فتح، ارسال ۳ تراک میکسر اول با تاخیر مواجه شد. عدم اعمال توقف زمانی به کل شیفت.</span>
  </div>
</div>
```

### ۸. کامپوننت صفحه‌بندی (Pagination)
```html
<div class="flex items-center justify-between px-4 py-3 bg-white border-t border-slate-200 text-xs text-slate-600">
  <div class="flex items-center gap-2">
    <span>نمایش ۱ تا ۲۵ از مجموع ۱۸۴ رکورد</span>
  </div>
  <div class="flex items-center gap-1">
    <button class="h-8 px-2.5 rounded-lg border border-slate-200 hover:bg-slate-50 flex items-center justify-center">
      <span class="material-symbols-outlined text-[16px]">chevron_right</span>
    </button>
    <button class="h-8 w-8 rounded-lg bg-blue-700 text-white font-mono font-bold">1</button>
    <button class="h-8 w-8 rounded-lg border border-slate-200 hover:bg-slate-50 text-slate-700 font-mono">2</button>
    <button class="h-8 w-8 rounded-lg border border-slate-200 hover:bg-slate-50 text-slate-700 font-mono">3</button>
    <button class="h-8 px-2.5 rounded-lg border border-slate-200 hover:bg-slate-50 flex items-center justify-center">
      <span class="material-symbols-outlined text-[16px]">chevron_left</span>
    </button>
  </div>
</div>
```

---

## ۵. تعاملات پیشنهادی با HTMX (HTMX Integration Guidelines)


> **Implementation Boundary**
>
> HTMX is optional and may only be used when the required URL, view,
> permission, service, workflow and backend behavior already exist in
> the application.
>
> The examples in this section are illustrative UI patterns only.
> They must not be interpreted as requirements to create new endpoints,
> approval workflows, permissions, services or business logic.
>
> If the existing application does not support the interaction,
> preserve the current server-rendered Django behavior.


برای تعاملات بدون نیاز به جاوااسکریپت سنگین:
1. **جستجو و فیلتر زنده جدول داده:**
   ```html
   <input type="text" name="search"
          hx-get="{% url 'workforce_table' %}"
          hx-trigger="keyup changed delay:300ms"
          hx-target="#table-container"
          hx-indicator="#search-spinner">
   ```
2. **تغییر تب‌های وضعیتی:**
   ```html
   <button hx-get="{% url 'ncr_list' %}?status=rejected"
           hx-target="#ncr-table-body"
           hx-swap="innerHTML">
     مردود شده‌ها
   </button>
   ```
