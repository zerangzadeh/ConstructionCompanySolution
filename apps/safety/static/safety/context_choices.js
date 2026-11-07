(() => {
    document.querySelectorAll("[data-safety-context-form]").forEach((form) => {
        const project = form.elements.namedItem("project");
        const fields = [...form.querySelectorAll("[data-safety-context]")];
        if (!project || fields.length !== 4) return;
        const byName = Object.fromEntries(fields.map((field) => [field.name, field]));
        // Retain only server-authorized options; no tenant-wide lookup is needed.
        const choices = new Map(fields.map((field) => [field,
            [...field.options].filter((option) => option.value).map((option) => option.cloneNode(true)),
        ]));
        const status = document.createElement("p");
        status.className = "sr-only";
        status.setAttribute("role", "status");
        status.setAttribute("aria-live", "polite");
        form.append(status);

        const clearError = (field) => {
            field.removeAttribute("aria-invalid");
            field.closest(".erp-form-field")?.classList.remove("erp-form-field--invalid");
            document.getElementById(`${field.id}-errors`)?.remove();
            const describedBy = (field.getAttribute("aria-describedby") || "")
                .split(/\s+/).filter((id) => id && id !== `${field.id}-errors`);
            if (describedBy.length) field.setAttribute("aria-describedby", describedBy.join(" "));
            else field.removeAttribute("aria-describedby");
        };

        const render = (changed) => {
            const counts = [];
            // Parent fields are refreshed first, so descendants see cleared values.
            fields.forEach((field) => {
                const previous = field.value;
                const site = byName.site.value;
                const phase = byName.phase.value;
                const name = field.dataset.safetyContext;
                const ready = Boolean(project.value && (name !== "phase" || site));
                const options = ready ? choices.get(field).filter((option) => {
                    if (option.dataset.project !== project.value) return false;
                    if (name === "site") return true;
                    if (name === "phase") return option.dataset.site === site;
                    if (name === "activity") {
                        return (!option.dataset.site || option.dataset.site === site)
                            && (!option.dataset.phase || option.dataset.phase === phase);
                    }
                    return option.dataset.site === site && option.dataset.phase === phase;
                }) : [];
                const placeholder = !ready
                    ? (name === "phase" ? "ابتدا کارگاه را انتخاب کنید" : "ابتدا پروژه را انتخاب کنید")
                    : (options.length ? "انتخاب کنید (اختیاری)" : "گزینه سازگاری وجود ندارد");
                field.replaceChildren(new Option(placeholder, ""), ...options.map((option) => option.cloneNode(true)));
                field.value = options.some((option) => option.value === previous) ? previous : "";
                field.disabled = !ready || !options.length;
                const help = document.getElementById(`${field.id}-help`);
                if (help && (name === "site" || name === "phase")) {
                    help.textContent = !ready ? `${placeholder}.`
                        : (name === "site" ? "کارگاه‌های پروژه انتخاب‌شده." : "فازهای کارگاه انتخاب‌شده.");
                }
                const parents = {
                    site: ["project"],
                    phase: ["project", "site"],
                    activity: ["project", "site", "phase"],
                    daily_report: ["project", "site", "phase"],
                };
                if (changed && parents[name].includes(changed)) clearError(field);
                counts.push(`${field.labels?.[0]?.textContent.trim() || name}: ${options.length}`);
            });
            if (changed) status.textContent = `گزینه‌های محدوده به‌روز شدند. ${counts.join("، ")}`;
        };
        [project, byName.site, byName.phase].forEach((field) => {
            field.addEventListener("change", () => render(field.name));
        });
        // Restore compatible labels on validation responses and browser history.
        render();
        window.addEventListener("pageshow", () => render());
    });
})();
