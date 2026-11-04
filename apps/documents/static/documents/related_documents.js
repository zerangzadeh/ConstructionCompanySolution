/* Hash navigation only; document access is always resolved on the server. */
(() => {
    const update = () => {
        const active = location.hash === '#related-documents';
        document.querySelectorAll('[data-related-documents-nav]').forEach(link => {
            if (active) link.setAttribute('aria-current', 'location');
            else link.removeAttribute('aria-current');
            link.classList.toggle('is-current', active);
        });
        if (active) {
            document.querySelectorAll('.erp-project-tabs a[href="#overview"], .cd-journey a[href$="#overview"]').forEach(link => {
                link.removeAttribute('aria-current');
                link.classList.remove('is-current');
            });
        }
    };
    update();
    window.addEventListener('hashchange', update);
})();
