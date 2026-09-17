(() => {
    "use strict";
    const chart = document.querySelector("[data-position-chart-tree]");
    const list = document.querySelector("[data-position-chart-list]");
    const filter = document.querySelector("[data-position-chart-filter]");
    if (!chart || !list || !filter) return;

    const nodes = [...chart.querySelectorAll("[data-position-chart-node]")];
    const rows = [...list.querySelectorAll("[data-position-list-row]")];
    const tree = chart.querySelector(".position-hierarchy");
    const listFilterForm = document.getElementById("position-chart-list-filters");
    if (listFilterForm && !listFilterForm.querySelector("input[name='view']")) {
        const input = document.createElement("input");
        input.type = "hidden";
        input.name = "view";
        input.value = "list";
        listFilterForm.appendChild(input);
    }
    const applyFilter = () => {
        const selectedDepartment = filter.value;
        nodes.forEach((node) => {
            const matches = !selectedDepartment || node.dataset.departmentId === selectedDepartment;
            const containsMatch = [...node.querySelectorAll("[data-position-chart-node]")]
                .some((child) => child.dataset.departmentId === selectedDepartment);
            node.hidden = Boolean(selectedDepartment) && !matches && !containsMatch;
        });
        rows.forEach((row) => {
            row.hidden = Boolean(selectedDepartment)
                && row.dataset.departmentId !== selectedDepartment;
        });
        scheduleConnectorRender();
    };

    const renderConnectors = () => {
        if (!tree || chart.hidden) return;
        let connectors = chart.querySelector(".position-hierarchy__connectors");
        if (!connectors) {
            connectors = document.createElementNS("http://www.w3.org/2000/svg", "svg");
            connectors.classList.add("position-hierarchy__connectors");
            connectors.setAttribute("aria-hidden", "true");
            chart.prepend(connectors);
        }
        connectors.replaceChildren();
        const chartBox = chart.getBoundingClientRect();
        connectors.setAttribute("width", String(chart.scrollWidth));
        connectors.setAttribute("height", String(chart.scrollHeight));
        connectors.setAttribute("viewBox", `0 0 ${chart.scrollWidth} ${chart.scrollHeight}`);

        nodes.forEach((node) => {
            if (node.hidden || node.offsetParent === null) return;
            const children = [...node.querySelectorAll(
                ":scope > .position-hierarchy__children > [data-position-chart-node]",
            )].filter((child) => !child.hidden && child.offsetParent !== null);
            if (!children.length) return;

            const parentCard = node.querySelector(":scope > .position-hierarchy__card");
            const parentBox = parentCard.getBoundingClientRect();
            const childPoints = children.map((child) => {
                const cardBox = child.querySelector(":scope > .position-hierarchy__card").getBoundingClientRect();
                return {
                    x: cardBox.left - chartBox.left + chart.scrollLeft + cardBox.width / 2,
                    y: cardBox.top - chartBox.top + chart.scrollTop,
                };
            });
            const parentX = parentBox.left - chartBox.left + chart.scrollLeft + parentBox.width / 2;
            const parentBottom = parentBox.bottom - chartBox.top + chart.scrollTop;
            const lineY = parentBottom + Math.max(14, (Math.min(...childPoints.map((point) => point.y)) - parentBottom) / 2);
            const horizontalStart = Math.min(...childPoints.map((point) => point.x));
            const horizontalEnd = Math.max(...childPoints.map((point) => point.x));
            const verticals = childPoints.map((point) => `M ${point.x} ${lineY} V ${point.y}`).join(" ");
            const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
            path.setAttribute("d", `M ${parentX} ${parentBottom} V ${lineY} M ${horizontalStart} ${lineY} H ${horizontalEnd} ${verticals}`);
            connectors.append(path);
        });
    };

    const scheduleConnectorRender = () => window.requestAnimationFrame(renderConnectors);
    filter.addEventListener("change", applyFilter);
    document.querySelectorAll("[data-position-chart-view]").forEach((button) => {
        button.addEventListener("click", () => {
            const showTree = button.dataset.positionChartView === "tree";
            chart.hidden = !showTree;
            list.hidden = showTree;
            document.querySelectorAll("[data-position-chart-view]").forEach((candidate) => {
                const isSelected = candidate === button;
                candidate.classList.toggle("is-active", isSelected);
                candidate.setAttribute("aria-pressed", String(isSelected));
            });
            if (showTree) scheduleConnectorRender();
        });
    });
    window.addEventListener("resize", scheduleConnectorRender);
    if (document.fonts?.ready) document.fonts.ready.then(scheduleConnectorRender);
    if (tree && "ResizeObserver" in window) {
        new ResizeObserver(scheduleConnectorRender).observe(tree);
    }
    scheduleConnectorRender();
})();
