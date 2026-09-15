(() => {
    "use strict";

    const monetaryNames = new Set([
        "amount",
        "budget",
        "contract_value",
        "cost",
        "max_amount",
        "min_amount",
        "total_amount",
        "unit_price",
        "value_change",
    ]);
    const digitMap = {"۰": "0", "۱": "1", "۲": "2", "۳": "3", "۴": "4", "۵": "5", "۶": "6", "۷": "7", "۸": "8", "۹": "9", "٠": "0", "١": "1", "٢": "2", "٣": "3", "٤": "4", "٥": "5", "٦": "6", "٧": "7", "٨": "8", "٩": "9"};
    const normalizeDigits = (value) => String(value || "").replace(/[۰-۹٠-٩]/g, (digit) => digitMap[digit]);
    const stripMoney = (value) => normalizeDigits(value).replace(/ریال|IRR|USD|EUR|GBP|AED/gi, "").replace(/[،,\s]/g, "");

    function formatMoney(value) {
        const raw = stripMoney(value);
        if (!raw || raw === "-") return raw;
        const sign = raw.startsWith("-") ? "-" : "";
        const unsigned = sign ? raw.slice(1) : raw;
        const decimalIndex = unsigned.indexOf(".");
        const integerPart = (decimalIndex >= 0 ? unsigned.slice(0, decimalIndex) : unsigned).replace(/\D/g, "");
        const decimalPart = decimalIndex >= 0 ? unsigned.slice(decimalIndex + 1).replace(/\D/g, "") : null;
        const formattedInteger = (integerPart || "0").replace(/\B(?=(\d{3})+(?!\d))/g, ",");
        return `${sign}${formattedInteger}${decimalPart === null ? "" : `.${decimalPart}`}`;
    }

    function fieldName(input) {
        const parts = String(input.name || "").split("-");
        return parts[parts.length - 1];
    }

    function labelFor(input) {
        const id = input.id;
        if (!id) return "";
        const escaped = window.CSS?.escape ? CSS.escape(id) : id.replace(/([:.\[\],=@])/g, "\\$1");
        return input.form?.querySelector(`label[for="${escaped}"]`)?.textContent.trim() || document.querySelector(`label[for="${escaped}"]`)?.textContent.trim() || "";
    }

    function isMonetaryInput(input) {
        if (!(input instanceof HTMLInputElement) || input.type === "hidden" || input.type === "submit" || input.type === "checkbox" || input.type === "radio") return false;
        if (monetaryNames.has(fieldName(input))) return true;
        return /^(مبلغ|بودجه|ارزش قرارداد|قیمت واحد|هزینه|هزینه نهایی|تغییر ارزش)/.test(labelFor(input));
    }

    function restoreCaret(input, significantBefore) {
        if (significantBefore === 0) {
            input.setSelectionRange(0, 0);
            return;
        }
        let seen = 0;
        let position = input.value.length;
        for (let index = 0; index < input.value.length; index += 1) {
            if (/[\d.]/.test(input.value[index])) seen += 1;
            if (seen >= significantBefore) {
                position = index + 1;
                break;
            }
        }
        input.setSelectionRange(position, position);
    }

    function formatInput(input) {
        const selection = input.selectionStart ?? input.value.length;
        const significantBefore = normalizeDigits(input.value.slice(0, selection)).replace(/[^\d.]/g, "").length;
        const formatted = formatMoney(input.value);
        if (formatted !== input.value) {
            input.value = formatted;
            restoreCaret(input, significantBefore);
        }
    }

    function enhanceInput(input) {
        if (input.dataset.moneyEnhanced || !isMonetaryInput(input)) return;
        input.dataset.moneyEnhanced = "true";
        input.dataset.originalType = input.type;
        input.type = "text";
        input.inputMode = "decimal";
        input.autocomplete = "off";
        input.dir = "ltr";
        input.classList.add("erp-money-input");
        input.value = formatMoney(input.value);

        const wrap = document.createElement("div");
        wrap.className = "erp-money-wrap";
        input.parentNode.insertBefore(wrap, input);
        wrap.appendChild(input);
        const unit = document.createElement("span");
        unit.className = "erp-money-unit";
        unit.textContent = "ریال";
        unit.id = `${input.id || input.name}-currency-unit`;
        wrap.appendChild(unit);
        input.setAttribute("aria-describedby", [input.getAttribute("aria-describedby"), unit.id].filter(Boolean).join(" "));

        input.addEventListener("input", () => formatInput(input));
        input.addEventListener("blur", () => { input.value = formatMoney(input.value); });
        input.addEventListener("paste", () => window.setTimeout(() => formatInput(input), 0));
    }

    function prepareForm(form) {
        const inputs = [...form.querySelectorAll("[data-money-enhanced]")];
        inputs.forEach((input) => { input.value = stripMoney(input.value); });
        window.setTimeout(() => inputs.forEach((input) => {
            if (document.contains(input)) input.value = formatMoney(input.value);
        }), 0);
    }

    function formatNumericText(target) {
        if (!target || target.dataset.moneyDisplayEnhanced) return;
        const text = target.textContent.trim();
        const match = normalizeDigits(text).match(/-?\d[\d,]*(?:\.\d+)?/);
        if (!match) return;
        const formatted = formatMoney(match[0]).replace(/\.0+$/, "").replace(/(\.\d*?[1-9])0+$/, "$1");
        const walker = document.createTreeWalker(target, NodeFilter.SHOW_TEXT);
        const textNodes = [];
        while (walker.nextNode()) textNodes.push(walker.currentNode);
        for (const node of textNodes) {
            const normalized = normalizeDigits(node.nodeValue);
            if (normalized.includes(match[0])) {
                node.nodeValue = normalized.replace(match[0], formatted);
                break;
            }
        }
        textNodes.forEach((node) => { node.nodeValue = node.nodeValue.replace(/\s*(IRR|ریال)\s*/gi, " "); });
        target.append(document.createTextNode(" ریال"));
        target.classList.add("erp-money-display");
        target.dataset.moneyDisplayEnhanced = "true";
    }

    function enhanceMoneyTables(root) {
        root.querySelectorAll?.("table").forEach((table) => {
            const headers = [...table.querySelectorAll("thead th")];
            const moneyColumns = headers.map((header, index) => {
                const text = header.textContent.trim();
                return /^(مبلغ|بودجه(?:\s*\(.+\))?|ارزش قرارداد|قیمت واحد|بها|جمع|برآورد مصوب|هزینه واقعی|انحراف|دریافت|پرداخت|خالص جریان نقدی)$/.test(text) ? index : -1;
            }).filter((index) => index >= 0);
            if (!moneyColumns.length) return;
            table.querySelectorAll("tbody tr").forEach((row) => {
                const cells = [...row.children].filter((cell) => cell.matches("td, th"));
                moneyColumns.forEach((index) => formatNumericText(cells[index]));
            });
        });
    }

    function enhanceLabeledMoney(root) {
        root.querySelectorAll?.("p, dt, h2, h3, span").forEach((label) => {
            const text = label.textContent.trim();
            const isMoneyLabel = /مبلغ|بودجه|ارزش قرارداد|قیمت واحد|هزینه ثبت‌شده|برآورد مصوب|مانده برآورد|انحراف|جریان نقدی|گردش وجوه نقد/.test(text) || /^(دریافت‌ها|پرداخت‌ها)$/.test(text);
            if (!isMoneyLabel) return;
            const target = label.tagName === "DT" ? label.nextElementSibling : label.nextElementSibling;
            if (target && /^-?[۰-۹٠-٩\d,.]+(?:\s*(IRR|ریال))?$/.test(target.textContent.trim())) formatNumericText(target);
        });
        root.querySelectorAll?.("*").forEach((element) => {
            if (element.closest("form") || ["OPTION", "SELECT", "INPUT", "TEXTAREA", "SCRIPT", "STYLE", "CODE", "PRE"].includes(element.tagName)) return;
            [...element.childNodes].filter((node) => node.nodeType === Node.TEXT_NODE && /\b(IRR|USD|EUR|GBP|AED)\b/.test(node.nodeValue)).forEach((node) => {
                node.nodeValue = node.nodeValue.replace(/\b(IRR|USD|EUR|GBP|AED)\b/g, "ریال");
            });
        });
    }

    function initialize(root = document) {
        if (root.matches?.("input")) enhanceInput(root);
        root.querySelectorAll?.("input").forEach(enhanceInput);
        enhanceMoneyTables(root);
        enhanceLabeledMoney(root);
    }

    document.addEventListener("submit", (event) => prepareForm(event.target), true);
    document.addEventListener("DOMContentLoaded", () => {
        initialize();
        new MutationObserver((mutations) => mutations.forEach((mutation) => mutation.addedNodes.forEach((node) => {
            if (node.nodeType === Node.ELEMENT_NODE) initialize(node);
        }))).observe(document.body, {childList: true, subtree: true});
    }, {once: true});
})();
