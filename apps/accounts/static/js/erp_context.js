(() => {
    // Metadata is emitted only for choices already scoped by the server form.
    document.querySelectorAll("select[data-local-parent]").forEach((select) => {
        const parent = document.getElementById(select.dataset.localParent);
        if (!parent || parent.form !== select.form) return;
        const choices = [...select.options].map((option) => option.cloneNode(true));
        const render = () => {
            const previous = select.value;
            select.replaceChildren(...choices.filter((option) =>
                !option.value || (parent.value && option.dataset.parentValue === parent.value)
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
                ? `پروژه مؤثر این ثبت: ${selected.textContent}`
                : "پروژه مؤثر این ثبت هنوز انتخاب نشده است.";
        };
        project.addEventListener("change", render);
        render();
    });
})();
