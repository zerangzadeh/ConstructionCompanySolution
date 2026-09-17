(() => {
    "use strict";

    const debounceMs = 400;
    const timers = new WeakMap();

    const navigateWithFilters = (form) => {
        const url = new URL(window.location.href);
        const controls = [...form.elements].filter((control) => control.name && !control.disabled);
        const names = new Set(controls.map((control) => control.name));
        names.forEach((name) => url.searchParams.delete(name));
        controls.forEach((control) => {
            if ((control.type === "checkbox" || control.type === "radio") && !control.checked) return;
            const value = control.value.trim();
            if (value) url.searchParams.append(control.name, value);
        });
        [...url.searchParams.keys()].forEach((key) => {
            if (!url.searchParams.get(key)?.trim()) url.searchParams.delete(key);
        });
        if (url.searchParams.has("page")) url.searchParams.set("page", "1");
        const query = url.searchParams.toString();
        window.location.assign(`${url.pathname}${query ? `?${query}` : ""}${url.hash}`);
    };

    const schedule = (form, control) => {
        window.clearTimeout(timers.get(form));
        if (control.tagName === "SELECT" || !control.value.trim()) {
            navigateWithFilters(form);
            return;
        }
        timers.set(form, window.setTimeout(() => navigateWithFilters(form), debounceMs));
    };

    const mountFilterRows = () => {
        document.querySelectorAll("template[id$='-row']").forEach((template) => {
            const formId = template.id.slice(0, -4);
            const head = document.querySelector("main table thead");
            if (!head || head.querySelector(`[data-table-filter-row='${formId}']`)) return;
            const fragment = template.content.cloneNode(true);
            fragment.querySelector("tr")?.setAttribute("data-table-filter-row", formId);
            head.appendChild(fragment);
        });
    };

    const bindFilterForms = () => {
        document.querySelectorAll("[data-table-filter-form], form[method='get']").forEach((form) => {
            if (form.dataset.tableFilterBound) return;
            form.dataset.tableFilterBound = "true";
            form.addEventListener("submit", (event) => {
                event.preventDefault();
                navigateWithFilters(form);
            });
            form.addEventListener("input", (event) => {
                if (event.target.matches("input[type='search'], input[type='text'], input:not([type]), input[data-jalali-date]")) {
                    schedule(form, event.target);
                }
            });
            form.addEventListener("change", (event) => {
                if (event.target.matches("select")) schedule(form, event.target);
            });
        });
        document.querySelectorAll("[data-table-filter-clear]").forEach((link) => {
            if (link.dataset.tableFilterBound) return;
            link.dataset.tableFilterBound = "true";
            link.addEventListener("click", (event) => {
                event.preventDefault();
                const url = new URL(window.location.href);
                const form = link.closest("[data-table-filter-controls]")?.querySelector("form") || link.closest("form");
                document.querySelectorAll("form[method='get']").forEach((getForm) => {
                    [...getForm.elements].filter((control) => control.name).forEach((control) => url.searchParams.delete(control.name));
                });
                if (url.searchParams.has("page")) url.searchParams.set("page", "1");
                const query = url.searchParams.toString();
                window.location.assign(`${url.pathname}${query ? `?${query}` : ""}${url.hash}`);
            });
        });
    };

    const sortKeyForHeader = (label) => {
        const path = window.location.pathname.toLowerCase();
        const normalized = label.replace(/\s+/g, " ").trim();
        if (/عملیات|اقدام|ارتباط|دلیل دریافت|شرح$|مبدأ/.test(normalized)) return "";
        if (normalized === "کد و نام") {
            if (path.includes("warehouse")) return "warehouse";
            if (path.includes("equipment")) return "equipment";
            if (path.includes("position")) return "position";
            if (path.includes("team")) return "team";
            return "name";
        }
        if (normalized.startsWith("کد پروژه")) return "code";
        if (normalized.startsWith("نام پروژه")) return "name";
        if (normalized === "کد فاز") return "code";
        if (normalized === "نام فاز") return "name";
        if (normalized.startsWith("شماره قرارداد")) return "number";
        if (normalized.startsWith("شماره برآورد")) return "number";
        if (normalized.startsWith("شماره پرداخت")) return "number";
        if (normalized.startsWith("شماره سفارش")) return "number";
        if (normalized.startsWith("شماره رسید")) return "number";
        if (normalized === "شماره") return "number";
        if (normalized.startsWith("شماره تراکنش")) return "number";
        if (normalized.startsWith("شماره و عنوان")) return path.includes("maintenance") ? "record" : "title";
        if (normalized.startsWith("شماره و نام")) return "number";
        if (normalized === "سند") return "document";
        if (normalized === "کد و عنوان") return "position";
        if (normalized === "کد و نام واحد") return "name";
        if (normalized === "واحد بالادست") return "parent";
        if (normalized === "کد کارگاه") return "code";
        if (normalized === "نام کارگاه") return "name";
        if (normalized === "نشانی") return "address";
        if (normalized === "مصالح") return "material";
        if (normalized === "تجهیز") return "equipment";
        if (normalized === "سفارش خرید") return "order";
        if (normalized === "نام مصالح") return "name";
        if (normalized === "نماد") return "symbol";
        if (normalized === "اعشار") return "decimal_places";
        if (normalized === "واحد") return "unit";
        if (normalized === "عنوان" || normalized.includes("عنوان و پروژه")) return "title";
        if (normalized === "طرف قرارداد" || normalized === "طرف حساب") return "counterparty";
        if (normalized === "تأمین‌کننده") return "supplier";
        if (normalized === "پروژه" || normalized.startsWith("پروژه /")) return "project";
        if (normalized.startsWith("پروژه و کارگاه")) return "project";
        if (normalized === "فاز") return "phase";
        if (normalized === "واحد و سمت") return path.includes("employee") ? "position" : "phase";
        if (normalized === "وضعیت") return "status";
        if (normalized === "اولویت") return "priority";
        if (normalized === "نوع") {
            if (path.includes("document")) return "document_type";
            if (path.includes("quality")) return "issue_type";
            if (path.includes("safety")) return "incident_type";
            if (path.includes("part")) return "kind";
            return "type";
        }
        if (normalized === "نوع تجهیز") return "equipment_type";
        if (normalized === "نوع تصدی") return "holder_type";
        if (normalized === "دسته" || normalized === "دسته‌بندی") return "category";
        if (normalized === "مالکیت") return "ownership";
        if (normalized === "محل") return "location";
        if (normalized === "کارمند") return "employee";
        if (normalized === "گروه کاری") return "team";
        if (normalized === "سرپرست") return "lead";
        if (normalized === "مسئولیت" || normalized.includes("مسئولیت در پروژه")) return "role";
        if (normalized === "شروع" || normalized === "تاریخ شروع") return "start_date";
        if (normalized === "بازه") return path.includes("assignment") ? "start_date" : "";
        if (normalized === "شروع برنامه") return "planned_start";
        if (normalized === "پایان برنامه") return "planned_end";
        if (normalized === "تاریخ پایان") return "end_date";
        if (normalized === "تاریخ" || normalized === "تاریخ گزارش") {
            if (path.includes("report")) return "reporting_date";
            if (path.includes("expense")) return "incurred_on";
            if (path.includes("inventory")) return "occurred_at";
            if (path.includes("maintenance")) return "scheduled_date";
            return "paid_on";
        }
        if (normalized === "تاریخ نیاز") return "required_by";
        if (normalized === "زمان شناسایی") return "identified_at";
        if (normalized === "زمان وقوع") return "occurred_at";
        if (normalized === "زمان") return "occurred_at";
        if (normalized === "مهلت") return "due_at";
        if (normalized === "نسخه جاری") return "version";
        if (normalized === "ارزش قرارداد") return "value";
        if (normalized === "مبلغ") return "amount";
        if (normalized === "نیروی کار") return "labor_count";
        if (normalized === "شدت") return "severity";
        if (normalized === "شرح هزینه") return "description";
        if (normalized === "شرح") return "description";
        if (normalized === "پروژه / فاز") return "project";
        if (normalized === "واحد شرکتی") return "department";
        if (normalized === "کد") return "code";
        if (normalized === "نام") return "name";
        if (normalized === "نام یا نماد") return "name";
        if (normalized === "نام نمایشی") return "name";
        if (normalized === "نویسنده") return "author";
        if (normalized === "شناسه مالیاتی") return "tax_id";
        if (normalized === "مقدار" || normalized === "تعداد") return "quantity";
        return "";
    };

    const enhanceSortHeaders = () => {
        if (!document.querySelector("[data-table-filter-controls], [data-table-filter-form]")) return;
        document.querySelectorAll("main table thead tr:not([data-table-filter-row])").forEach((row) => {
            row.querySelectorAll("th").forEach((cell) => {
                if (cell.querySelector("a, input, select, button")) return;
                const label = cell.textContent;
                const sortKey = sortKeyForHeader(label);
                if (!sortKey) return;
                const url = new URL(window.location.href);
                const currentKey = url.searchParams.get("sort") || "";
                const currentDirection = url.searchParams.get("direction") || "asc";
                const current = currentKey === sortKey ? currentDirection : "none";
                const nextDirection = current === "asc" ? "desc" : "asc";
                url.searchParams.delete("page");
                [...url.searchParams.keys()].forEach((key) => {
                    if (!url.searchParams.get(key)?.trim()) url.searchParams.delete(key);
                });
                url.searchParams.set("sort", sortKey);
                url.searchParams.set("direction", nextDirection);
                const link = document.createElement("a");
                link.href = `${url.pathname}?${url.searchParams.toString()}${url.hash}`;
                link.className = "inline-flex items-center gap-1 rounded px-1 py-0.5 transition hover:bg-blue-50 hover:text-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1";
                link.setAttribute("aria-label", `مرتب‌سازی ${label.trim()}`);
                const text = document.createElement("span");
                text.textContent = label.trim();
                const indicator = document.createElement("span");
                indicator.className = "text-[10px] leading-none text-slate-400";
                indicator.setAttribute("aria-hidden", "true");
                indicator.textContent = current === "asc" ? "↑" : current === "desc" ? "↓" : "↕";
                link.append(text, indicator);
                cell.textContent = "";
                cell.appendChild(link);
                cell.setAttribute("aria-sort", current === "asc" ? "ascending" : current === "desc" ? "descending" : "none");
            });
        });
    };

    const init = () => {
        mountFilterRows();
        bindFilterForms();
        enhanceSortHeaders();
    };
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, { once: true });
    else init();
})();
