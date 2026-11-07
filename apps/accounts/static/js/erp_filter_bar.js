/* Layout enhancement only. GET URLs and server-rendered controls own state. */
(() => {
    'use strict';
    let rowMenusBound = false;
    window.addEventListener('pageshow', () => {
        // Opt-in lists restore server-rendered GET values after browser history
        // restores a form's later, unsaved edits over the previous result page.
        document.querySelectorAll('form[data-restore-filter-state]').forEach(form => {
            form.reset();
            form.querySelectorAll('select').forEach(select => {
                if (select.tomselect) {
                    select.tomselect.setValue([...select.selectedOptions].map(option => option.value), true);
                }
            });
        });
    });
    const mount = () => {
        document.querySelectorAll('[data-filter-options]').forEach(panel => {
            if (panel.dataset.responsiveBound) return;
            const quick = panel.querySelector('.erp-list-quick');
            let summary = panel.querySelector('.erp-list-options__summary');
            const enhancedDisclosure = panel.closest('[data-field-list], .erp-workspace--timekeeping');
            if (enhancedDisclosure) {
                // Preserve the live controls while avoiding native details
                // content remaining hidden around enhanced selects in Chrome.
                const replacement = document.createElement('div');
                for (const attribute of panel.attributes) {
                    if (attribute.name !== 'open') replacement.setAttribute(attribute.name, attribute.value);
                }
                const button = document.createElement('button');
                button.type = 'button';
                button.className = summary.className;
                button.append(...summary.childNodes);
                summary.replaceWith(button);
                summary = button;
                replacement.append(...panel.childNodes);
                panel.replaceWith(replacement);
                panel = replacement;
                quick.id ||= panel.closest('form').id + '-quick';
                summary.setAttribute('aria-controls', quick.id);
                summary.addEventListener('click', () => {
                    panel.open = !panel.open;
                    quick.hidden = !panel.open;
                    summary.setAttribute('aria-expanded', String(panel.open));
                });
            }
            panel.dataset.responsiveBound = 'true';
            const desktop = window.matchMedia(panel.hasAttribute('data-filter-options-expanded') ? '(min-width: 0px)' : '(min-width: 1280px)');
            const bar = panel.closest('[data-filter-bar]');
            const more = bar.querySelector('[data-more-filters]');
            const toggle = bar.querySelector('[data-more-toggle]');
            const clear = bar.querySelector('[data-context-preserving-clear]');
            const chips = bar.querySelector('.erp-list-chips');
            const actions = bar.querySelector('.erp-list-filter-actions');
            const syncMore = () => {
                if (!more) return;
                more.hidden = desktop.matches && !more.open;
                toggle?.setAttribute('aria-expanded', String(more.open));
            };
            const sync = () => {
                panel.open = desktop.matches;
                if (enhancedDisclosure) {
                    quick.hidden = !panel.open;
                    summary.setAttribute('aria-expanded', String(panel.open));
                }
                // One clear link: beside Apply on desktop, with visible chips
                // when the mobile quick-filter disclosure is collapsed.
                if (clear && !bar.hasAttribute('data-reference-layout')) (desktop.matches ? actions : chips)?.append(clear);
                if (toggle) toggle.hidden = !desktop.matches;
                if (more) more.querySelector('summary').hidden = desktop.matches;
                syncMore();
            };
            toggle?.addEventListener('click', () => { more.open = !more.open; });
            more?.addEventListener('toggle', syncMore);
            sync();
            desktop.addEventListener('change', sync);
        });
        if (!rowMenusBound && document.querySelector('.erp-contracts-list .erp-list-row-menu')) {
            rowMenusBound = true;
            const openMenus = () => document.querySelectorAll('.erp-contracts-list .erp-list-row-menu[open]');
            document.addEventListener('toggle', event => {
                const menu = event.target;
                if (!menu.matches?.('.erp-contracts-list .erp-list-row-menu') || !menu.open) return;
                openMenus().forEach(other => { if (other !== menu) other.open = false; });
            }, true);
            document.addEventListener('click', event => {
                openMenus().forEach(menu => { if (!menu.contains(event.target)) menu.open = false; });
            });
            document.addEventListener('keydown', event => {
                if (event.key !== 'Escape') return;
                openMenus().forEach(menu => {
                    if (menu.contains(document.activeElement)) menu.querySelector('summary').focus();
                    menu.open = false;
                });
            });
        }
    };
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mount);
    else mount();
    document.addEventListener('htmx:afterSwap', mount);
})();
