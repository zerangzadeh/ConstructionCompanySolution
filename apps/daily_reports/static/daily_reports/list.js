/* Optional page filters: an empty parent means all authorized child choices. */
(() => {
    document.querySelectorAll('.erp-daily-list select[data-daily-parent]').forEach(select => {
        const parent = document.getElementById(select.dataset.dailyParent);
        if (!parent || parent.form !== select.form) return;
        const choices = [...select.options].map(option => option.cloneNode(true));
        const render = () => {
            const previous = select.value;
            select.replaceChildren(...choices.filter(option =>
                !option.value || !parent.value || option.dataset.parentValue === parent.value
            ).map(option => option.cloneNode(true)));
            select.value = [...select.options].some(option => option.value === previous) ? previous : '';
            select.dispatchEvent(new Event('change', {bubbles: true}));
        };
        parent.addEventListener('change', render);
        render();
    });
})();
