"use strict";

(() => {
    function initializeAdminSidebarAccordion() {
        const sidebar = document.getElementById("nav-sidebar");
        if (!sidebar) {
            return;
        }

        const groups = Array.from(sidebar.querySelectorAll("details.erp-admin-sidebar-group"));
        const filter = document.getElementById("nav-filter");

        groups.forEach((group) => {
            group.open = group.classList.contains("current-app");
            group.addEventListener("toggle", () => {
                if (!group.open || sidebar.dataset.filtering === "true") {
                    return;
                }
                groups.forEach((otherGroup) => {
                    if (otherGroup !== group) {
                        otherGroup.open = false;
                    }
                });
            });
        });

        if (!filter) {
            return;
        }

        filter.addEventListener("input", () => {
            window.requestAnimationFrame(() => {
                const isFiltering = filter.value.trim() !== "";
                sidebar.dataset.filtering = String(isFiltering);
                groups.forEach((group) => {
                    if (isFiltering) {
                        const rows = Array.from(group.querySelectorAll("tbody tr"));
                        group.open = rows.some((row) => row.style.display !== "none");
                    } else {
                        group.open = group.classList.contains("current-app");
                    }
                });
            });
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initializeAdminSidebarAccordion, {once: true});
    } else {
        initializeAdminSidebarAccordion();
    }
})();
