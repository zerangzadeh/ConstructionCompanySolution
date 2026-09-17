(() => {
    "use strict";

    const shell = document.querySelector("[data-org-chart]");
    if (!shell) return;

    const treeView = shell.querySelector("[data-tree-view]");
    const listView = shell.querySelector("[data-list-view]");
    const tree = shell.querySelector("[data-chart-tree]");
    const branches = [...shell.querySelectorAll("[data-chart-branch]")];
    const nodes = [...shell.querySelectorAll("[data-chart-node]")];
    const rows = [...shell.querySelectorAll("[data-list-row]")];
    const cards = [...shell.querySelectorAll("[data-chart-card]")];
    const panels = [...shell.querySelectorAll("[data-details-panel]")];
    const drawer = shell.querySelector("[data-details-drawer]");
    const placeholder = shell.querySelector("[data-details-placeholder]");
    const search = shell.querySelector("[data-chart-search]");
    const departmentFilter = shell.querySelector("[data-department-filter]");
    const statusFilter = shell.querySelector("[data-status-filter]");
    const noResults = shell.querySelector("[data-no-results]");
    let zoom = 1;

    const normalize = (value) => value.trim().toLocaleLowerCase("fa").replaceAll("ي", "ی").replaceAll("ك", "ک");

    const showDetails = (departmentId) => {
        cards.forEach((card) => {
            const owner = card.closest("[data-chart-node]");
            const cardDepartmentId = owner?.dataset.departmentId || card.dataset.departmentId;
            card.classList.toggle("is-selected", cardDepartmentId === departmentId);
        });
        panels.forEach((panel) => { panel.hidden = panel.dataset.departmentId !== departmentId; });
        if (placeholder) placeholder.hidden = Boolean(departmentId);
        if (drawer && departmentId) drawer.classList.add("is-open");
    };

    const relationMatches = (node, matchingNodes) => matchingNodes.some((match) => node === match || node.contains(match) || match.contains(node));

    const renderConnectors = () => {
        if (!tree) return;
        let connectors = tree.querySelector(".org-chart-connectors");
        if (!connectors) {
            connectors = document.createElementNS("http://www.w3.org/2000/svg", "svg");
            connectors.classList.add("org-chart-connectors");
            connectors.setAttribute("aria-hidden", "true");
            tree.prepend(connectors);
        }
        connectors.replaceChildren();
        const treeBox = tree.getBoundingClientRect();
        const scale = tree.offsetWidth ? treeBox.width / tree.offsetWidth : 1;
        connectors.setAttribute("width", String(tree.offsetWidth));
        connectors.setAttribute("height", String(tree.offsetHeight));
        connectors.setAttribute("viewBox", `0 0 ${tree.offsetWidth} ${tree.offsetHeight}`);

        branches.forEach((node) => {
            if (node.hidden || node.offsetParent === null || node.classList.contains("is-collapsed")) return;
            const children = [...node.querySelectorAll(":scope > ul > [data-chart-branch]")]
                .filter((child) => !child.hidden && child.offsetParent !== null);
            if (!children.length) return;

            const parentCard = node.querySelector(":scope > .org-chart-card");
            const childCards = children.map((child) => child.querySelector(":scope > .org-chart-card"));
            const parentBox = parentCard.getBoundingClientRect();
            const childBoxes = childCards.map((card) => card.getBoundingClientRect());
            const parentX = (parentBox.left - treeBox.left + parentBox.width / 2) / scale;
            const parentBottom = (parentBox.bottom - treeBox.top) / scale;
            const childPoints = childBoxes.map((box) => ({
                x: (box.left - treeBox.left + box.width / 2) / scale,
                y: (box.top - treeBox.top) / scale,
            }));
            const lineY = parentBottom + Math.max(12, (Math.min(...childPoints.map((point) => point.y)) - parentBottom) / 2);
            const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
            const horizontalStart = Math.min(...childPoints.map((point) => point.x));
            const horizontalEnd = Math.max(...childPoints.map((point) => point.x));
            const verticals = childPoints.map((point) => `M ${point.x} ${lineY} V ${point.y}`).join(" ");
            path.setAttribute("d", `M ${parentX} ${parentBottom} V ${lineY} M ${horizontalStart} ${lineY} H ${horizontalEnd} ${verticals}`);
            connectors.append(path);
        });

    };

    const scheduleConnectorRender = () => window.requestAnimationFrame(renderConnectors);

    const applyFilters = () => {
        const query = normalize(search?.value || "");
        const departmentId = departmentFilter?.value || "";
        const active = statusFilter?.value || "";
        const queryMatches = query ? nodes.filter((node) => normalize(node.querySelector("[data-chart-card]").textContent).includes(query)) : nodes;
        const selectedNode = departmentId ? nodes.find((node) => node.dataset.departmentId === departmentId) : null;
        const statusMatches = active ? nodes.filter((node) => node.dataset.active === active) : nodes;

        nodes.forEach((node) => {
            const matchesQuery = !query || relationMatches(node, queryMatches);
            const matchesDepartment = !selectedNode || node === selectedNode || node.contains(selectedNode) || selectedNode.contains(node);
            const matchesStatus = !active || relationMatches(node, statusMatches);
            node.hidden = !(matchesQuery && matchesDepartment && matchesStatus);
        });
        rows.forEach((row) => {
            const matchesQuery = !query || normalize(row.textContent).includes(query);
            const matchesDepartment = !departmentId || row.dataset.departmentId === departmentId;
            const matchesStatus = !active || row.dataset.active === active;
            row.hidden = !(matchesQuery && matchesDepartment && matchesStatus);
        });
        if (noResults) noResults.hidden = nodes.some((node) => !node.hidden);
        scheduleConnectorRender();
    };

    shell.querySelectorAll("[data-view]").forEach((button) => {
        button.addEventListener("click", () => {
            const isTree = button.dataset.view === "tree";
            treeView.hidden = !isTree;
            listView.hidden = isTree;
            shell.querySelectorAll("[data-view]").forEach((candidate) => {
                const selected = candidate === button;
                candidate.classList.toggle("is-active", selected);
                candidate.setAttribute("aria-pressed", String(selected));
            });
        });
    });

    cards.forEach((card) => {
        const open = () => {
            const owner = card.closest("[data-chart-node]");
            showDetails(owner?.dataset.departmentId || card.dataset.departmentId);
        };
        card.addEventListener("click", open);
        card.addEventListener("keydown", (event) => {
            if (event.key === "Enter" || event.key === " ") { event.preventDefault(); open(); }
        });
    });

    shell.querySelectorAll("[data-collapse-branch]").forEach((button) => {
        button.addEventListener("click", (event) => {
            event.stopPropagation();
            const node = button.closest("[data-chart-branch]");
            const collapsed = node.classList.toggle("is-collapsed");
            button.setAttribute("aria-expanded", String(!collapsed));
            scheduleConnectorRender();
        });
    });

    [search, departmentFilter, statusFilter].forEach((control) => {
        if (control) control.addEventListener(control === search ? "input" : "change", applyFilters);
    });

    const setZoom = (nextZoom) => {
        zoom = Math.min(1.35, Math.max(.65, nextZoom));
        if (tree) tree.style.transform = `scale(${zoom})`;
        scheduleConnectorRender();
    };
    shell.querySelector("[data-zoom-in]")?.addEventListener("click", () => setZoom(zoom + .1));
    shell.querySelector("[data-zoom-out]")?.addEventListener("click", () => setZoom(zoom - .1));
    shell.querySelector("[data-fullscreen]")?.addEventListener("click", () => {
        const canvas = shell.querySelector(".org-chart-canvas-wrap");
        if (!document.fullscreenElement) canvas?.requestFullscreen();
        else document.exitFullscreen();
    });
    shell.querySelector("[data-close-details]")?.addEventListener("click", () => {
        drawer?.classList.remove("is-open");
        showDetails("");
    });

    if (nodes.length) showDetails(nodes[0].dataset.departmentId);
    window.addEventListener("resize", scheduleConnectorRender);
    if (document.fonts?.ready) document.fonts.ready.then(scheduleConnectorRender);
    if (tree && "ResizeObserver" in window) {
        new ResizeObserver(scheduleConnectorRender).observe(tree);
    }
    shell.querySelector("[data-organization-chart-details]")?.addEventListener(
        "toggle",
        scheduleConnectorRender,
    );
    scheduleConnectorRender();
})();
