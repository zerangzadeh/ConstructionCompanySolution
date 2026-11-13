/* Project section overflow only. Native details remains usable without JavaScript. */
(() => {
    const photo = document.querySelector('[data-project-photo]');
    const fallback = document.querySelector('[data-project-photo-fallback]');
    if (photo && fallback) {
        const showPhoto = () => {
            const usable = photo.naturalWidth >= 160 && photo.naturalHeight >= 90;
            photo.hidden = !usable;
            fallback.hidden = usable;
        };
        photo.addEventListener('load', showPhoto);
        photo.addEventListener('error', showPhoto);
        if (photo.complete) showPhoto();
    }
    const menu = document.querySelector('.project-nav-more');
    if (!menu) return;
    const trigger = menu.querySelector('summary');
    menu.addEventListener('keydown', event => {
        if (event.key === 'Escape' && menu.open) {
            menu.open = false;
            trigger.focus();
        }
    });
    menu.addEventListener('click', event => {
        if (event.target.closest('a')) menu.open = false;
    });
    document.addEventListener('click', event => {
        if (!menu.contains(event.target)) menu.open = false;
    });
})();
