(() => {
    "use strict";

    const monthNames = [
        "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
        "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
    ];
    const weekNames = ["ش", "ی", "د", "س", "چ", "پ", "ج"];
    const gregorianMonthNames = {
        january: 1, jan: 1, "ژانویه": 1,
        february: 2, feb: 2, "فوریه": 2,
        march: 3, mar: 3, "مارس": 3,
        april: 4, apr: 4, "آوریل": 4,
        may: 5, "مه": 5,
        june: 6, jun: 6, "ژوئن": 6,
        july: 7, jul: 7, "ژوئیه": 7,
        august: 8, aug: 8, "اوت": 8,
        september: 9, sep: 9, sept: 9, "سپتامبر": 9,
        october: 10, oct: 10, "اکتبر": 10,
        november: 11, nov: 11, "نوامبر": 11,
        december: 12, dec: 12, "دسامبر": 12,
    };
    const digitMap = {"۰": "0", "۱": "1", "۲": "2", "۳": "3", "۴": "4", "۵": "5", "۶": "6", "۷": "7", "۸": "8", "۹": "9", "٠": "0", "١": "1", "٢": "2", "٣": "3", "٤": "4", "٥": "5", "٦": "6", "٧": "7", "٨": "8", "٩": "9"};
    const normalizeDigits = (value) => String(value || "").replace(/[۰-۹٠-٩]/g, (digit) => digitMap[digit]);
    const toPersianDigits = (value) => String(value).replace(/[0-9]/g, (digit) => "۰۱۲۳۴۵۶۷۸۹"[Number(digit)]);
    const pad = (value) => String(value).padStart(2, "0");

    function gregorianToJalali(gy, gm, gd) {
        const monthDays = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334];
        const adjustedYear = gm > 2 ? gy + 1 : gy;
        let days = 355666 + (365 * gy) + Math.floor((adjustedYear + 3) / 4) - Math.floor((adjustedYear + 99) / 100) + Math.floor((adjustedYear + 399) / 400) + gd + monthDays[gm - 1];
        let jy = -1595 + (33 * Math.floor(days / 12053));
        days %= 12053;
        jy += 4 * Math.floor(days / 1461);
        days %= 1461;
        if (days > 365) {
            jy += Math.floor((days - 1) / 365);
            days = (days - 1) % 365;
        }
        const jm = days < 186 ? 1 + Math.floor(days / 31) : 7 + Math.floor((days - 186) / 30);
        const jd = days < 186 ? 1 + (days % 31) : 1 + ((days - 186) % 30);
        return [jy, jm, jd];
    }

    function jalaliToGregorian(jy, jm, jd) {
        jy += 1595;
        let days = -355668 + (365 * jy) + (Math.floor(jy / 33) * 8) + Math.floor(((jy % 33) + 3) / 4) + jd + (jm < 7 ? (jm - 1) * 31 : ((jm - 7) * 30) + 186);
        let gy = 400 * Math.floor(days / 146097);
        days %= 146097;
        if (days > 36524) {
            gy += 100 * Math.floor(--days / 36524);
            days %= 36524;
            if (days >= 365) days += 1;
        }
        gy += 4 * Math.floor(days / 1461);
        days %= 1461;
        if (days > 365) {
            gy += Math.floor((days - 1) / 365);
            days = (days - 1) % 365;
        }
        const gd = days + 1;
        const leap = (gy % 4 === 0 && gy % 100 !== 0) || gy % 400 === 0;
        const monthLengths = [0, 31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
        let gm = 1;
        let remaining = gd;
        while (gm <= 12 && remaining > monthLengths[gm]) remaining -= monthLengths[gm++];
        return [gy, gm, remaining];
    }

    const formatJalali = ([year, month, day]) => toPersianDigits(`${year}/${pad(month)}/${pad(day)}`);
    const parseJalali = (value) => {
        const match = normalizeDigits(value).trim().match(/^(\d{4})\/(\d{2})\/(\d{2})/);
        if (!match) return null;
        const result = match.slice(1, 4).map(Number);
        if (result[1] < 1 || result[1] > 12 || result[2] < 1 || result[2] > daysInJalaliMonth(result[0], result[1])) return null;
        return result;
    };
    const parseGregorian = (value) => {
        const match = normalizeDigits(value).match(/(19|20)\d{2}[\/-]\d{1,2}[\/-]\d{1,2}/);
        if (!match) return null;
        const parts = match[0].split(/[\/-]/).map(Number);
        return parts[1] >= 1 && parts[1] <= 12 && parts[2] >= 1 && parts[2] <= 31 ? parts : null;
    };

    function convertVisibleDates(root = document.body) {
        if (!root) return;
        const skipped = new Set(["SCRIPT", "STYLE", "TEXTAREA", "INPUT", "CODE", "PRE"]);
        const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
        const nodes = [];
        while (walker.nextNode()) {
            const parent = walker.currentNode.parentElement;
            if (parent && !skipped.has(parent.tagName) && !parent.closest("[data-no-jalali]")) nodes.push(walker.currentNode);
        }
        nodes.forEach((node) => {
            let text = node.nodeValue;
            text = text.replace(/([۰-۹٠-٩0-9]{4})[\/-]([۰-۹٠-٩0-9]{1,2})[\/-]([۰-۹٠-٩0-9]{1,2})/g, (_, year, month, day) => {
                const normalizedYear = Number(normalizeDigits(year));
                if (normalizedYear < 1900 || normalizedYear > 2099) return _;
                return formatJalali(gregorianToJalali(normalizedYear, Number(normalizeDigits(month)), Number(normalizeDigits(day))));
            });
            const namedPattern = /([۰-۹٠-٩0-9]{1,2})\s+([A-Za-z]+|ژانویه|فوریه|مارس|آوریل|مه|ژوئن|ژوئیه|اوت|سپتامبر|اکتبر|نوامبر|دسامبر)[،,]?\s+([۰-۹٠-٩0-9]{4})/gi;
            text = text.replace(namedPattern, (whole, day, name, year) => {
                const month = gregorianMonthNames[String(name).toLowerCase()];
                return month ? formatJalali(gregorianToJalali(Number(normalizeDigits(year)), month, Number(normalizeDigits(day)))) : whole;
            });
            if (text !== node.nodeValue) node.nodeValue = text;
        });
    }

    let activeInput = null;
    let visibleMonth = null;

    function daysInJalaliMonth(year, month) {
        if (month <= 6) return 31;
        if (month <= 11) return 30;
        const current = jalaliToGregorian(year, 12, 29);
        const next = jalaliToGregorian(year + 1, 1, 1);
        const currentDate = new Date(current[0], current[1] - 1, current[2]);
        const nextDate = new Date(next[0], next[1] - 1, next[2]);
        return Math.round((nextDate - currentDate) / 86400000) === 2 ? 30 : 29;
    }

    function ensurePopover(input) {
        let wrap = input.closest(".erp-jalali-wrap");
        if (!wrap) {
            wrap = document.createElement("div");
            wrap.className = "erp-jalali-wrap";
            input.parentNode.insertBefore(wrap, input);
            wrap.appendChild(input);
        }
        let trigger = wrap.querySelector(":scope > .erp-jalali-trigger");
        if (!trigger) {
            trigger = document.createElement("button");
            trigger.type = "button";
            trigger.className = "erp-jalali-trigger";
            const fieldLabel = Array.from(input.labels || []).map((label) => label.textContent.trim()).join(" ");
            trigger.setAttribute("aria-label", fieldLabel ? `باز کردن تقویم شمسی: ${fieldLabel}` : "باز کردن تقویم شمسی");
            trigger.innerHTML = "<span aria-hidden=\"true\">▦</span>";
            wrap.appendChild(trigger);
        }
        let popover = wrap.querySelector(":scope > .erp-jalali-popover");
        if (!popover) {
            popover = document.createElement("div");
            popover.className = "erp-jalali-popover";
            popover.hidden = true;
            wrap.appendChild(popover);
        }
        trigger.addEventListener("click", () => openPicker(input));
        return popover;
    }

    function renderPicker() {
        if (!activeInput || !visibleMonth) return;
        const popover = ensurePopover(activeInput);
        const [year, month] = visibleMonth;
        const selected = parseJalali(activeInput.value);
        const now = new Date();
        const today = gregorianToJalali(now.getFullYear(), now.getMonth() + 1, now.getDate());
        const firstGregorian = jalaliToGregorian(year, month, 1);
        const firstWeekday = (new Date(firstGregorian[0], firstGregorian[1] - 1, firstGregorian[2]).getDay() + 1) % 7;
        popover.innerHTML = `<div class="erp-jalali-header"><button class="erp-jalali-nav" type="button" data-month="next" aria-label="ماه بعد">‹</button><strong class="erp-jalali-title">${monthNames[month - 1]} ${toPersianDigits(year)}</strong><button class="erp-jalali-nav" type="button" data-month="previous" aria-label="ماه قبل">›</button></div><div class="erp-jalali-week">${weekNames.map((day) => `<span>${day}</span>`).join("")}</div><div class="erp-jalali-days"></div>`;
        const days = popover.querySelector(".erp-jalali-days");
        for (let index = 0; index < firstWeekday; index += 1) days.insertAdjacentHTML("beforeend", '<span class="erp-jalali-day-spacer"></span>');
        for (let day = 1; day <= daysInJalaliMonth(year, month); day += 1) {
            const button = document.createElement("button");
            button.type = "button";
            button.className = "erp-jalali-day";
            button.textContent = toPersianDigits(day);
            button.dataset.day = String(day);
            if (selected && selected[0] === year && selected[1] === month && selected[2] === day) button.classList.add("is-selected");
            if (today[0] === year && today[1] === month && today[2] === day) button.classList.add("is-today");
            days.appendChild(button);
        }
        popover.querySelector('[data-month="previous"]').addEventListener("click", () => changeMonth(-1));
        popover.querySelector('[data-month="next"]').addEventListener("click", () => changeMonth(1));
        days.addEventListener("click", (event) => {
            const button = event.target.closest("[data-day]");
            if (!button) return;
            const datePart = formatJalali([year, month, Number(button.dataset.day)]);
            const timePart = activeInput.dataset.jalaliMode === "datetime" ? ` ${toPersianDigits(normalizeDigits(activeInput.value).split(/\s+/)[1] || "00:00")}` : "";
            activeInput.value = datePart + timePart;
            activeInput.setCustomValidity("");
            popover.hidden = true;
            activeInput.dispatchEvent(new Event("change", {bubbles: true}));
        });
    }

    function changeMonth(offset) {
        let [year, month] = visibleMonth;
        month += offset;
        if (month < 1) { year -= 1; month = 12; }
        if (month > 12) { year += 1; month = 1; }
        visibleMonth = [year, month];
        renderPicker();
    }

    function openPicker(input) {
        document.querySelectorAll(".erp-jalali-popover").forEach((item) => { item.hidden = true; });
        activeInput = input;
        const parsed = parseJalali(input.value);
        if (parsed) visibleMonth = parsed.slice(0, 2);
        else {
            const now = new Date();
            visibleMonth = gregorianToJalali(now.getFullYear(), now.getMonth() + 1, now.getDate()).slice(0, 2);
        }
        const popover = ensurePopover(input);
        const rect = input.getBoundingClientRect();
        const popoverWidth = Math.min(304, window.innerWidth - 32);
        popover.style.top = `${Math.min(rect.bottom + 6, window.innerHeight - 340)}px`;
        popover.style.left = `${Math.max(16, Math.min(rect.right - popoverWidth, window.innerWidth - popoverWidth - 16))}px`;
        popover.hidden = false;
        renderPicker();
    }

    function enhanceInput(input) {
        if (input.dataset.jalaliEnhanced || input.disabled || input.readOnly) return;
        const originalType = input.type;
        const isAdminDate = input.classList.contains("vDateField");
        const isJalaliDate = input.dataset.jalaliDate === "date" || input.dataset.jalaliDate === "datetime";
        if (originalType !== "date" && originalType !== "datetime-local" && !isAdminDate && !isJalaliDate) return;
        input.dataset.jalaliEnhanced = "true";
        input.dataset.jalaliMode = input.dataset.jalaliDate || (originalType === "datetime-local" ? "datetime" : "date");
        input.dataset.inputMask = "####/##/##";
        const original = normalizeDigits(input.value);
        const gregorian = parseGregorian(original);
        if (gregorian) {
            const datePart = formatJalali(gregorianToJalali(...gregorian));
            const timeMatch = original.match(/[T\s](\d{1,2}:\d{2})/);
            input.value = datePart + (input.dataset.jalaliMode === "datetime" ? ` ${toPersianDigits(timeMatch ? timeMatch[1] : "00:00")}` : "");
        }
        input.type = "text";
        input.classList.add("erp-jalali-input");
        input.placeholder = input.dataset.jalaliMode === "datetime" ? "۱۴۰۵/۰۶/۲۳ ۱۴:۳۰" : "۱۴۰۵/۰۶/۲۳";
        input.setAttribute("inputmode", "numeric");
        input.setAttribute("autocomplete", "off");
        input.setAttribute("maxlength", input.dataset.jalaliMode === "datetime" ? "16" : "10");
        input.addEventListener("input", () => {
            const suffix = input.dataset.jalaliMode === "datetime" ? normalizeDigits(input.value).slice(10) : "";
            const digits = normalizeDigits(input.value).replace(/\D/g, "").slice(0, 8);
            const masked = digits.length <= 4 ? digits : `${digits.slice(0, 4)}/${digits.slice(4, 6)}${digits.length > 6 ? `/${digits.slice(6, 8)}` : ""}`;
            input.value = masked + (suffix && masked.length === 10 ? suffix : "");
            if (input.value.length >= 10 && !parseJalali(input.value)) input.setCustomValidity("تاریخ جلالی واردشده معتبر نیست.");
            else input.setCustomValidity("");
        });
        ensurePopover(input);
        input.addEventListener("focus", () => openPicker(input));
    }

    function prepareForm(form) {
        let valid = true;
        form.querySelectorAll("[data-jalali-enhanced]").forEach((input) => {
            if (!input.value.trim()) return;
            const parsed = parseJalali(input.value);
            if (!parsed) {
                input.setCustomValidity("تاریخ را با قالب شمسی صحیح وارد کنید.");
                valid = false;
                return;
            }
            input.setCustomValidity("");
            const gregorian = jalaliToGregorian(...parsed);
            const datePart = `${gregorian[0]}-${pad(gregorian[1])}-${pad(gregorian[2])}`;
            if (input.dataset.jalaliMode === "datetime") {
                const timeMatch = normalizeDigits(input.value).match(/\s(\d{1,2}):(\d{2})/);
                if (!timeMatch) {
                    input.setCustomValidity("تاریخ و ساعت را با قالب صحیح وارد کنید.");
                    valid = false;
                    return;
                }
                input.value = `${datePart}T${pad(timeMatch[1])}:${timeMatch[2]}`;
            } else input.value = datePart;
        });
        if (!valid) {
            form.querySelector("[data-jalali-enhanced]:invalid")?.reportValidity();
        }
        return valid;
    }

    function initialize(root = document) {
        if (root.matches?.('input[type="date"], input[type="datetime-local"], input.vDateField, input[data-jalali-date]')) enhanceInput(root);
        root.querySelectorAll?.('input[type="date"], input[type="datetime-local"], input.vDateField, input[data-jalali-date]').forEach(enhanceInput);
        convertVisibleDates(root === document ? document.body : root);
    }

    document.addEventListener("submit", (event) => {
        if (!prepareForm(event.target)) event.preventDefault();
    }, true);
    document.addEventListener("click", (event) => {
        if (!event.target.closest(".erp-jalali-wrap")) document.querySelectorAll(".erp-jalali-popover").forEach((item) => { item.hidden = true; });
    });
    document.addEventListener("DOMContentLoaded", () => {
        initialize();
        new MutationObserver((mutations) => mutations.forEach((mutation) => mutation.addedNodes.forEach((node) => {
            if (node.nodeType === Node.ELEMENT_NODE) initialize(node);
        }))).observe(document.body, {childList: true, subtree: true});
    }, {once: true});
})();
