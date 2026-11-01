/* Reflect qualified project selection without changing submitted values. */
(() => {
    "use strict";
    document.addEventListener("DOMContentLoaded", () => {
        document.querySelectorAll("[data-create-page]").forEach((page) => {
            const project = page.querySelector("select[name=project]");
            const summary = page.querySelector("[data-create-project-context]");
            if (!project || !summary) return;
            const reflectProject = () => {
                summary.textContent = project.value
                    ? project.selectedOptions[0]?.textContent || "انتخاب پروژه در فرم"
                    : "انتخاب پروژه در فرم";
            };
            project.addEventListener("change", reflectProject);
            reflectProject();
        });
    }, {once: true});
})();
