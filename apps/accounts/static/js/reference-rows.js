(() => {
    document.querySelectorAll("[data-reference-rows]").forEach((widget) => {
        const list = widget.querySelector("[data-reference-list]");
        const add = () => list.append(widget.querySelector("template").content.cloneNode(true));
        widget.querySelector("[data-reference-add]").addEventListener("click", add);
        widget.addEventListener("click", (event) => {
            if (event.target.closest("[data-reference-remove]")) event.target.closest("[data-reference-row]").remove();
        });
        if (!list.children.length) { add(); add(); }
    });
})();
