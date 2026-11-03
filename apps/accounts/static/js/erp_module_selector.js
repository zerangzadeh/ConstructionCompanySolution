/* Native modal focus/inert behavior; navigation authority stays server-side. */
(() => {
  'use strict';
  const trigger = document.querySelector('[data-module-trigger]');
  const drawer = document.querySelector('#erp-module-selector');
  if (!trigger || !drawer || drawer.dataset.mounted) return;
  drawer.dataset.mounted = 'true';
  const row = drawer.querySelector('.erp-module-selector__row');
  const previous = drawer.querySelector('[data-module-previous]');
  const next = drawer.querySelector('[data-module-next]');
  const position = drawer.querySelector('[data-module-position]');
  const reducedMotion = () => matchMedia('(prefers-reduced-motion: reduce)').matches;
  const updateScroll = () => {
    const overflow = row.scrollWidth - row.clientWidth;
    const offset = Math.abs(row.scrollLeft); // RTL: zero is the right edge.
    previous.hidden = next.hidden = position.hidden = overflow <= 1;
    previous.setAttribute('aria-disabled', String(offset <= 1));
    next.setAttribute('aria-disabled', String(offset >= overflow - 1));
    const fraction = row.clientWidth / Math.max(row.scrollWidth, 1);
    position.firstElementChild.style.width = `${fraction * 100}%`;
    position.firstElementChild.style.transform = `translateX(${-offset * position.clientWidth / Math.max(row.scrollWidth, 1)}px)`;
  };
  previous.addEventListener('click', () => row.scrollBy({left: row.clientWidth * .8, behavior: reducedMotion() ? 'instant' : 'smooth'}));
  next.addEventListener('click', () => row.scrollBy({left: -row.clientWidth * .8, behavior: reducedMotion() ? 'instant' : 'smooth'}));
  row.addEventListener('scroll', updateScroll, {passive: true});
  new ResizeObserver(updateScroll).observe(row);
  row.addEventListener('keydown', event => {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
    const links = [...row.querySelectorAll('a[href]')];
    const index = links.indexOf(document.activeElement);
    if (index < 0) return;
    event.preventDefault();
    const target = event.key === 'Home' ? 0 : event.key === 'End' ? links.length - 1
      : Math.max(0, Math.min(links.length - 1, index + (event.key === 'ArrowLeft' ? 1 : -1)));
    links[target].focus({preventScroll: true});
    links[target].scrollIntoView({block: 'nearest', inline: 'nearest', behavior: reducedMotion() ? 'instant' : 'smooth'});
  });
  trigger.addEventListener('click', () => {
    if (drawer.open) return;
    drawer.showModal();
    document.documentElement.classList.add('erp-module-selector-open');
    trigger.setAttribute('aria-expanded', 'true');
    const active = drawer.querySelector('[aria-current]');
    const focus = active || drawer.querySelector('[data-module-close]');
    focus.focus({preventScroll: true});
    updateScroll();
    active?.scrollIntoView({block: 'nearest', inline: 'center', behavior: 'instant'});
  });
  drawer.querySelector('[data-module-close]').addEventListener('click', () => drawer.close());
  drawer.addEventListener('keydown', event => {
    if (event.key !== 'Tab') return;
    const controls = [...drawer.querySelectorAll('button:not([disabled]), a[href], [tabindex="0"]')].filter(control => control.getClientRects().length && getComputedStyle(control).visibility !== 'hidden');
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
