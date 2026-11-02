/* Native modal focus/inert behavior; navigation authority stays server-side. */
(() => {
  'use strict';
  const trigger = document.querySelector('[data-module-trigger]');
  const drawer = document.querySelector('#erp-module-selector');
  if (!trigger || !drawer || drawer.dataset.mounted) return;
  drawer.dataset.mounted = 'true';
  trigger.addEventListener('click', () => {
    if (drawer.open) return;
    drawer.showModal();
    document.documentElement.classList.add('erp-module-selector-open');
    trigger.setAttribute('aria-expanded', 'true');
    const active = drawer.querySelector('[aria-current]');
    const focus = active || drawer.querySelector('[data-module-close]');
    focus.focus({preventScroll: true});
    active?.scrollIntoView({block: 'nearest', inline: 'center', behavior: 'instant'});
  });
  drawer.querySelector('[data-module-close]').addEventListener('click', () => drawer.close());
  drawer.addEventListener('keydown', event => {
    if (event.key !== 'Tab') return;
    const controls = [...drawer.querySelectorAll('button:not([disabled]), a[href], [tabindex="0"]')];
    const first = controls[0], last = controls.at(-1);
    if ((!event.shiftKey && document.activeElement === last) ||
        (event.shiftKey && document.activeElement === first)) {
      event.preventDefault();
      (event.shiftKey ? last : first).focus();
    }
  });
  drawer.addEventListener('click', event => {
    const rect = drawer.getBoundingClientRect();
    const backdrop = event.target === drawer &&
      (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom);
    if (backdrop || event.target.closest('a[href]')) drawer.close();
  });
  // Native Escape cancellation closes the dialog and dispatches the same event.
  drawer.addEventListener('close', () => {
    document.documentElement.classList.remove('erp-module-selector-open');
    trigger.setAttribute('aria-expanded', 'false');
    trigger.focus({preventScroll: true});
  });
})();
