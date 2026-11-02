/* Position existing reference row menus within the viewport. No domain state. */
(() => {
    'use strict';
    const root = document.querySelector('[data-field-list]');
    if (!root) return;
    const closeMenus = () => root.querySelectorAll('.erp-list-row-menu[open]').forEach(menu => { menu.open = false; });
    root.addEventListener('toggle', event => {
        const menu = event.target;
        if (!menu.matches('.erp-list-row-menu') || !menu.open) return;
        const panel = menu.querySelector('.erp-list-row-menu__items');
        if (!panel) return;
        const anchor = menu.querySelector('summary').getBoundingClientRect();
        const width = panel.getBoundingClientRect().width;
        const height = panel.getBoundingClientRect().height;
        panel.style.left = Math.max(12, Math.min(anchor.left, innerWidth - width - 12)) + 'px';
        panel.style.right = 'auto';
        panel.style.top = Math.max(12, Math.min(anchor.bottom + 5, innerHeight - height - 12)) + 'px';
    }, true);
    // A viewport popup must not drift away from its source when scrolling.
    document.addEventListener('scroll', event => {
        if (!event.target.closest?.('.erp-list-row-menu__items')) closeMenus();
    }, true);
    window.addEventListener('resize', closeMenus);
})();
