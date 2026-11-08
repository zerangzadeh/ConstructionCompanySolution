/* Presentation only: native successful controls and audited POST remain intact. */
(() => {
    'use strict';
    const root = document.querySelector('[data-role-workspace]');
    if (!root) return;
    const form = root.querySelector('[data-role-editor]');
    if (!form) return;
    const groups = [...root.querySelectorAll('[data-permission-group]')];
    const rows = [...root.querySelectorAll('[data-permission-row]')];
    const search = root.querySelector('#permission-search');
    const selectedOnly = root.querySelector('#selected-permissions');
    const format = new Intl.NumberFormat('fa-IR');
    const normalize = value => value.toLowerCase().replace(/ي/g, 'ی').replace(/ك/g, 'ک').replace(/[\u200c\u064b-\u065f]/g, '');
    let filtering = false;
    let previousOpen = [];
    const indexed = rows.map(row => ({row, input: row.querySelector('input'), text: normalize(row.textContent)}));
    function update() {
        const terms = normalize(search.value.trim()).split(/\s+/).filter(Boolean);
        const active = !!(terms.length || selectedOnly.checked);
        if (active && !filtering) previousOpen = groups.map(group => group.open);
        let matches = 0;
        for (const {row, input, text} of indexed) {
            row.hidden = !(terms.every(term => text.includes(term)) && (!selectedOnly.checked || input.checked));
            if (!row.hidden) matches++;
        }
        for (const [index, group] of groups.entries()) {
            const visible = [...group.querySelectorAll('[data-permission-row]')].some(row => !row.hidden);
            group.hidden = !visible;
            if (active) group.open = visible;
            else if (filtering) group.open = previousOpen[index];
            group.querySelector('[data-group-selected]').textContent = format.format(group.querySelectorAll('input[type=checkbox]:checked').length);
        }
        filtering = active;
        root.querySelector('[data-selected-count]').textContent = format.format(indexed.filter(item => item.input.checked).length);
        root.querySelector('[data-permission-empty]').hidden = matches > 0;
        root.querySelector('[data-permission-result]').textContent = active ? `${format.format(matches)} مجوز مطابق فیلتر` : 'گروه موردنظر را باز کنید و مجوزها را بررسی کنید.';
    }
    root.querySelector('[data-permission-tools]').hidden = false;
    search.addEventListener('input', update);
    selectedOnly.addEventListener('change', update);
    form.addEventListener('change', update);
    root.querySelector('[data-collapse-groups]').addEventListener('click', () => {
        search.value = '';
        selectedOnly.checked = false;
        update();
        groups.forEach(group => { group.open = false; });
    });
    update();
    if (form.dataset.editing !== 'true') return;
    const snapshot = () => JSON.stringify([...new FormData(form).entries()]);
    const baseline = snapshot();
    let submitting = false;
    const dirty = () => snapshot() !== baseline;
    const state = root.querySelector('[data-unsaved-state]');
    const showDirty = () => { state.textContent = dirty() ? 'تغییرات ذخیره‌نشده دارید.' : 'تغییری برای ذخیره وجود ندارد.'; };
    form.addEventListener('input', showDirty);
    form.addEventListener('change', showDirty);
    showDirty();
    form.addEventListener('submit', event => {
        // The shared confirmation/duplicate-submit adapter owns consequential submits.
        queueMicrotask(() => { submitting = !event.defaultPrevented; });
    });
    window.addEventListener('pageshow', () => { submitting = false; });
    window.addEventListener('beforeunload', event => {
        if (!submitting && dirty()) { event.preventDefault(); event.returnValue = ''; }
    });
    document.addEventListener('click', async event => {
        const link = event.target.closest('a[href]');
        if (!link || event.defaultPrevented || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey || link.target === '_blank' || !dirty()) return;
        const destination = new URL(link.href, location.href);
        if (destination.pathname === location.pathname && destination.search === location.search && destination.hash) return;
        event.preventDefault();
        if (!window.BoniraFeedback) return;
        const accepted = await BoniraFeedback.confirm({title: 'تغییرات ذخیره‌نشده', text: 'با خروج از ویرایش، تغییرات ذخیره‌نشده کنار گذاشته می‌شوند.', confirmLabel: 'خروج از ویرایش'});
        if (accepted === true) { submitting = true; location.assign(link.href); }
    });
    // Native disclosures must reveal a hidden invalid control before focus.
    form.addEventListener('invalid', event => {
        const group = event.target.closest('[data-permission-group]');
        if (group) { group.hidden = false; group.open = true; }
    }, true);
})();
