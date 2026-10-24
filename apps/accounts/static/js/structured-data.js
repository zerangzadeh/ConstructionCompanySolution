/* Schema-neutral editing. Number lexemes are retained without JS numeric rounding. */
(() => {
    "use strict";
    class NumericValue { constructor(raw) { this.raw = raw; } }
    const numberPattern = /^-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?$/;
    const types = [["string", "متن"], ["number", "عدد"], ["boolean", "بله / خیر"], ["null", "بدون مقدار"], ["object", "مجموعه نام و مقدار"], ["array", "فهرست"]];
    const element = (tag, text, cls = "") => {
        const node = document.createElement(tag);
        node.textContent = text;
        node.className = cls;
        return node;
    };
    const button = (text, action) => {
        const node = element("button", text, "erp-btn erp-btn--secondary");
        node.type = "button";
        node.addEventListener("click", action);
        return node;
    };
    const parse = (raw) => JSON.parse(raw, (key, value, context) => {
        if (typeof value !== "number") return value;
        if (!context?.source) throw new Error("مرورگر باید نگهداری دقیق مقدارهای عددی را پشتیبانی کند؛ داده را در نمای فنی بررسی کنید.");
        return new NumericValue(context.source);
    });
    document.querySelectorAll("[data-structured-editor]").forEach((editor) => {
        const raw = editor.querySelector("textarea");
        const controls = editor.querySelector("[data-structured-controls]");
        const error = editor.querySelector("[data-structured-error]");
        let root;
        let rawDirty = false;
        const fail = (message) => { error.textContent = message; error.hidden = false; };
        const build = (value, label) => {
            const box = element("fieldset", "", "space-y-2 rounded-lg border border-slate-200 p-3");
            box.append(element("legend", label, "text-sm font-medium"));
            const type = element("select", "", "rounded border border-slate-300 p-2");
            type.setAttribute("aria-label", "نوع مقدار");
            types.forEach(([key, text]) => { const option = element("option", text); option.value = key; type.append(option); });
            type.value = value instanceof NumericValue ? "number" : value === null ? "null" : Array.isArray(value) ? "array" : typeof value;
            const body = element("div", "", "space-y-2");
            box.append(type, body);
            let read;
            const draw = (current) => {
                body.replaceChildren();
                if (type.value === "object" || type.value === "array") {
                    const rows = [];
                    const add = (name, content) => {
                        const row = element("div", "", "space-y-2 border-s-2 border-slate-200 ps-3");
                        const key = element("input", "", "w-full rounded border border-slate-300 p-2");
                        key.type = "text"; key.value = name; key.setAttribute("aria-label", "نام");
                        if (type.value === "object") row.append(key);
                        const child = build(content, "مقدار");
                        const entry = {row, key, child};
                        rows.push(entry);
                        row.append(child.box, button("حذف ردیف", () => { rows.splice(rows.indexOf(entry), 1); row.remove(); }));
                        body.insertBefore(row, addButton);
                    };
                    const addButton = button("افزودن ردیف", () => add("", ""));
                    body.append(addButton);
                    if (type.value === "array") (Array.isArray(current) ? current : []).forEach((item) => add("", item));
                    else if (current && !Array.isArray(current) && typeof current === "object") Object.entries(current).forEach(([key, item]) => add(key, item));
                    read = () => {
                        if (type.value === "array") return `[${rows.map((row) => row.child.read()).join(",")}]`;
                        const seen = new Set();
                        return `{${rows.map((row) => {
                            if (seen.has(row.key.value)) throw new Error("نام تکراری در یک مجموعه مجاز نیست.");
                            seen.add(row.key.value);
                            return `${JSON.stringify(row.key.value)}:${row.child.read()}`;
                        }).join(",")}}`;
                    };
                } else if (type.value === "null") read = () => "null";
                else if (type.value === "boolean") {
                    const input = element("select", "", "rounded border border-slate-300 p-2");
                    input.setAttribute("aria-label", "مقدار بله یا خیر");
                    [["true", "بله"], ["false", "خیر"]].forEach(([key, label]) => { const opt = element("option", label); opt.value = key; input.append(opt); });
                    input.value = current === true ? "true" : "false";
                    body.append(input); read = () => input.value;
                } else {
                    const input = element("textarea", "", "w-full rounded border border-slate-300 p-2");
                    input.rows = 2; input.setAttribute("aria-label", "مقدار");
                    input.value = current instanceof NumericValue ? current.raw : typeof current === "string" ? current : "";
                    body.append(input);
                    read = () => {
                        if (type.value === "string") return JSON.stringify(input.value);
                        if (!numberPattern.test(input.value)) throw new Error("مقدار عددی معتبر وارد کنید.");
                        return input.value;
                    };
                }
            };
            draw(value);
            type.addEventListener("change", () => draw(type.value === "object" ? {} : type.value === "array" ? [] : ""));
            return {box, read: () => read()};
        };
        const load = () => {
            try {
                root = build(parse(raw.value || raw.dataset.emptyValue), "داده‌ها");
                controls.replaceChildren(root.box); rawDirty = false; error.hidden = true;
            } catch (exc) { root = null; editor.querySelector("details").open = true; fail(exc.message); }
        };
        raw.addEventListener("input", () => { rawDirty = true; });
        editor.querySelector("[data-structured-apply]").addEventListener("click", load);
        editor.closest("form").addEventListener("submit", (event) => {
            if (!root || rawDirty) return; // Existing technical submissions retain their exact payload.
            try { raw.value = root.read(); error.hidden = true; }
            catch (exc) { event.preventDefault(); fail(exc.message); error.focus(); }
        });
        load();
    });
})();
