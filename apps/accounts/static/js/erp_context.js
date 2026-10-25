(() => {
    document.querySelectorAll("select[data-material-derived]").forEach((select) => {
        const name = document.getElementById(select.dataset.materialNameField);
        const unit = document.getElementById(select.dataset.materialUnitField);
        const unitChoice = document.getElementById(select.dataset.materialUnitChoice);
        if (!name || !unit || !unitChoice || [name, unit, unitChoice].some((field) => field.form !== select.form)) return;
        let wasDerived = false;
        const render = () => {
            const option = select.selectedOptions[0];
            const derived = Boolean(select.value && option?.dataset.materialName);
            name.readOnly = derived;
            unit.readOnly = derived;
            unitChoice.disabled = derived;
            if (derived) {
                name.value = option.dataset.materialName;
                unit.value = option.dataset.materialUnit;
                unitChoice.value = option.dataset.materialUnitId;
            } else if (wasDerived) {
                name.value = "";
                unit.value = "";
                unitChoice.value = "";
            }
            wasDerived = derived;
        };
        select.addEventListener("change", render);
        render();
    });

    // Metadata is emitted only for choices already scoped by the server form.
    document.querySelectorAll("select[data-local-parent]").forEach((select) => {
        const parent = document.getElementById(select.dataset.localParent);
        if (!parent || parent.form !== select.form) return;
        const choices = [...select.options].map((option) => option.cloneNode(true));
        const render = () => {
            const previous = select.value;
            const parentValue = select.dataset.localParentKey
                ? parent.selectedOptions[0]?.dataset[select.dataset.localParentKey]
                : parent.value;
            select.replaceChildren(...choices.filter((option) =>
                !option.value || (parent.value && parentValue && option.dataset.parentValue === parentValue)
            ).map((option) => option.cloneNode(true)));
            select.value = [...select.options].some((option) => option.value === previous) ? previous : "";
            select.disabled = !parent.value;
            select.dispatchEvent(new Event("change", { bubbles: true }));
        };
        parent.addEventListener("change", render);
        render();
    });

    const replaceOptions = (select, options, emptyLabel) => {
        const previous = select.value;
        select.replaceChildren(new Option(emptyLabel, ""));
        options.forEach(({ value, label }) => select.add(new Option(label, value)));
        if ([...select.options].some((option) => option.value === previous)) {
            select.value = previous;
        } else {
            select.value = "";
        }
        select.disabled = false;
        select.dispatchEvent(new Event("change", { bubbles: true }));
    };

    document.querySelectorAll("[data-context-project]").forEach((project) => {
        project.addEventListener("change", () => {
            const site = project.form?.querySelector("[data-context-site]");
            if (!site) return;
            site.value = "";
            site.disabled = !project.value;
        });
    });

    document.querySelectorAll("[data-cascade-project]").forEach((project) => {
        project.addEventListener("change", async () => {
            const form = project.form;
            if (!form) return;
            const targets = form.querySelectorAll("[data-cascade-field]");
            for (const select of targets) {
                const emptyLabel = select.dataset.emptyLabel || "انتخاب کنید";
                select.replaceChildren(new Option(emptyLabel, ""));
                select.disabled = true;
                if (!project.value) continue;
                const url = new URL(select.dataset.optionsUrl, window.location.origin);
                url.searchParams.set("project", project.value);
                url.searchParams.set("source", select.dataset.cascadeSource);
                url.searchParams.set("field", select.dataset.cascadeField);
                try {
                    const response = await fetch(url, {
                        headers: { Accept: "application/json" },
                        credentials: "same-origin",
                    });
                    if (!response.ok) throw new Error("scope denied");
                    const payload = await response.json();
                    replaceOptions(select, payload.options, emptyLabel);
                } catch (_error) {
                    select.replaceChildren(
                        new Option("گزینه مجاز در دسترس نیست", ""),
                    );
                    select.disabled = true;
                }
            }
        });
    });

    document.querySelectorAll("[data-mutation-context]").forEach((label) => {
        const form = label.closest("section")?.nextElementSibling;
        const project = form?.querySelector("[data-cascade-project]");
        if (!project) return;
        const render = () => {
            const selected = project.options[project.selectedIndex];
            label.textContent = selected?.value
                ? `پروژه این ثبت: ${selected.textContent}`
                : "پروژه این ثبت هنوز انتخاب نشده است.";
        };
        project.addEventListener("change", render);
        render();
    });
})();
