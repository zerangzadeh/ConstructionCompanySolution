/* Layout enhancement only. GET URLs and server-rendered controls own state. */
(() => {
    'use strict';
    const mount = () => {
        document.querySelectorAll('[data-filter-options]').forEach(panel => {
            if (panel.dataset.responsiveBound) return;
            panel.dataset.responsiveBound = 'true';
            const desktop = window.matchMedia('(min-width: 1280px)');
            const bar = panel.closest('[data-filter-bar]');
            const more = bar.querySelector('[data-more-filters]');
            const toggle = bar.querySelector('[data-more-toggle]');
            const syncMore = () => {
                if (!more) return;
                more.hidden = desktop.matches && !more.open;
                toggle?.setAttribute('aria-expanded', String(more.open));
            };
            const sync = () => {
                panel.open = desktop.matches;
                if (toggle) toggle.hidden = !desktop.matches;
                if (more) more.querySelector('summary').hidden = desktop.matches;
                syncMore();
            };
            toggle?.addEventListener('click', () => { more.open = !more.open; });
            more?.addEventListener('toggle', syncMore);
            sync();
            desktop.addEventListener('change', sync);
        });
    };
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mount);
    else mount();
    document.addEventListener('htmx:afterSwap', mount);
})();
