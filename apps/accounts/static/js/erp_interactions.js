/* Shared feedback boundary. The server owns validation, authorization and success. */
(() => {
  'use strict';
  if (window.BoniraFeedback) return;
  const levels = new Set(['success', 'error', 'warning', 'info']);
  const titles = {success: 'عملیات انجام شد', error: 'عملیات انجام نشد', warning: 'نیاز به بررسی', info: 'اطلاع‌رسانی'};
  const pending = new WeakSet(), confirmed = new WeakSet(), submitting = new WeakSet(), busy = new Map();
  const seen = new WeakSet(), responseSeen = new WeakSet();
  const queue = [];
  let showing = false, dialogPending = false;
  const defaults = {
    heightAuto: false, buttonsStyling: false, returnFocus: true,
    customClass: {popup: 'erp-interaction-popup', confirmButton: 'erp-btn erp-btn--primary', cancelButton: 'erp-btn erp-btn--secondary'},
    confirmButtonText: 'متوجه شدم', cancelButtonText: 'انصراف',
    showCloseButton: true, closeButtonAriaLabel: 'بستن پیام',
  };
  const safeLevel = value => levels.has(value) ? value : 'info';
  const motion = () => matchMedia('(prefers-reduced-motion: reduce)').matches
    ? {showClass: {popup: ''}, hideClass: {popup: ''}} : {};
  function fallback(text) {
    const node = document.createElement('p');
    node.className = 'erp-feedback-fallback';
    node.setAttribute('role', 'alert');
    node.textContent = text;
    (document.querySelector('main') || document.body).prepend(node);
  }
  async function drain() {
    if (showing || dialogPending || !queue.length) return;
    showing = true;
    const item = queue.shift(), level = safeLevel(item.level);
    try {
      if (!window.Swal) { if (!item.source) fallback(item.text); return; }
      await window.Swal.fire({...defaults, ...motion(), icon: level,
        iconColor: {success: '#15803d', error: '#b91c1c', warning: '#b45309', info: '#1563d6'}[level],
        titleText: item.modal ? (item.title || titles[level]) : item.text,
        text: item.modal ? item.text : undefined,
        toast: !item.modal, position: item.modal ? 'center' : 'top-start',
        showConfirmButton: Boolean(item.modal),
        timer: !item.modal && ['success', 'info'].includes(level) ? 6000 : undefined,
        timerProgressBar: !item.modal,
        didOpen: popup => {
          item.source?.setAttribute('hidden', '');
          const container = item.source?.closest('[data-feedback-messages]');
          if (container && !container.querySelector('[data-feedback-level]:not([hidden])')) container.hidden = true;
          popup.addEventListener('mouseenter', () => window.Swal.stopTimer());
          popup.addEventListener('mouseleave', () => { if (!popup.contains(document.activeElement)) window.Swal.resumeTimer(); });
          popup.addEventListener('focus', () => window.Swal.stopTimer(), true);
          popup.addEventListener('blur', event => {
            if (!popup.contains(event.relatedTarget) && !popup.matches(':hover')) window.Swal.resumeTimer();
          }, true);
          if (popup.contains(document.activeElement) || popup.matches(':hover')) window.Swal.stopTimer();
          popup.dataset.feedbackLevel = level;
        },
      });
    } finally { showing = false; drain(); }
  }
  function notify(level, text) {
    if (typeof text !== 'string' || !text.trim()) return;
    queue.push({level: safeLevel(level), text}); drain();
  }
  function alert(level, text, title) {
    if (typeof text !== 'string' || !text.trim()) return;
    queue.push({level: safeLevel(level), text, title: typeof title === 'string' ? title : '', modal: true}); drain();
  }
  async function confirm({title, text = '', confirmLabel = 'تأیید و ادامه', danger = false} = {}) {
    if (dialogPending || typeof title !== 'string' || !title) return false;
    if (!window.Swal) { fallback('نمایش تأیید ممکن نیست. صفحه را دوباره بارگذاری کنید.'); return false; }
    dialogPending = true;
    if (showing) window.Swal.close();
    try {
      const result = await window.Swal.fire({...defaults, ...motion(), titleText: title,
        text: typeof text === 'string' ? text : '', icon: danger ? 'warning' : 'question',
        iconColor: danger ? '#b45309' : '#1563d6',
        confirmButtonText: typeof confirmLabel === 'string' ? confirmLabel : 'تأیید و ادامه',
        showCancelButton: true, focusCancel: true, focusConfirm: false, allowOutsideClick: false,
        customClass: {...defaults.customClass, confirmButton: danger ? 'erp-btn erp-feedback-danger' : defaults.customClass.confirmButton},
      });
      return result.isConfirmed === true;
    } finally { dialogPending = false; drain(); }
  }
  function consume(root = document) {
    for (const node of root.querySelectorAll('[data-feedback-messages] [data-feedback-level]')) {
      if (seen.has(node)) continue;
      seen.add(node);
      queue.push({level: safeLevel(node.dataset.feedbackLevel), text: node.querySelector('[data-feedback-text]')?.textContent.trim() || '', source: node});
    }
    drain();
    const invalid = root.querySelector('.erp-form-field--invalid input, .erp-form-field--invalid select, .erp-form-field--invalid textarea');
    const summary = root.querySelector('[data-form-errors]');
    if (invalid?.form?.hasAttribute('data-focus-first-error') && !seen.has(invalid)) {
      seen.add(invalid);
      requestAnimationFrame(() => {
        const control = invalid.tomselect?.control_input ?? invalid;
        control.scrollIntoView({block: 'center'});
        control.focus({preventScroll: true});
      });
    }
    else if (summary && !seen.has(summary)) { seen.add(summary); summary.focus(); }
    else if (invalid && !seen.has(invalid)) { seen.add(invalid); invalid.focus(); }
  }
  function lock(form) {
    if (busy.has(form)) return;
    const buttons = [...form.querySelectorAll('button[type="submit"], button:not([type]), input[type="submit"]')];
    busy.set(form, {aria: form.getAttribute('aria-busy'), buttons: buttons.map(button => [button, button.getAttribute('aria-disabled')])});
    form.setAttribute('aria-busy', 'true');
    // Preserve successful controls (name/value) in the native/HTMX payload.
    buttons.forEach(button => button.setAttribute('aria-disabled', 'true'));
  }
  function unlock(form) {
    const state = busy.get(form);
    if (!state) return;
    if (state.aria === null) form.removeAttribute('aria-busy'); else form.setAttribute('aria-busy', state.aria);
    state.buttons.forEach(([button, value]) => value === null ? button.removeAttribute('aria-disabled') : button.setAttribute('aria-disabled', value));
    busy.delete(form);
  }
  function reset() { for (const form of busy.keys()) unlock(form); }
  window.BoniraFeedback = Object.freeze({notify, success: text => notify('success', text), error: text => notify('error', text),
    warning: text => notify('warning', text), info: text => notify('info', text), alert, confirm});
  window.BoniraInteractions = true; // Existing integration readiness marker.
  window.addEventListener('submit', async event => {
    const form = event.target, submitter = event.submitter;
    if (!(form instanceof HTMLFormElement)) return;
    if (busy.has(form) || submitting.has(form)) { event.preventDefault(); event.stopImmediatePropagation(); return; }
    const config = submitter?.hasAttribute('data-confirm-title') ? submitter : form;
    if (config.hasAttribute('data-confirm-title') && !confirmed.has(form)) {
      if (event.defaultPrevented) return;
      event.preventDefault(); event.stopImmediatePropagation();
      if (pending.has(form)) return;
      pending.add(form);
      try {
        const accepted = await confirm({title: config.dataset.confirmTitle, text: config.dataset.confirmText,
          confirmLabel: config.dataset.confirmLabel,
          danger: config.dataset.confirmDanger === 'true' || Boolean(submitter?.classList.contains('erp-btn--danger'))});
        if (!accepted || !form.isConnected || submitter?.disabled) return;
        confirmed.add(form);
        try { form.requestSubmit(submitter || undefined); } finally { confirmed.delete(form); }
      } finally { pending.delete(form); }
      return;
    }
    const method = (submitter?.getAttribute('formmethod') || form.method).toLowerCase();
    const target = submitter?.formTarget || form.target;
    if (method === 'post') submitting.add(form);
    queueMicrotask(() => {
      submitting.delete(form);
      if (!event.defaultPrevented && method === 'post' && (!target || target === '_self')) lock(form);
    });
  }, true);
  document.addEventListener('htmx:confirm', event => {
    if (!event.detail.question) return;
    event.preventDefault();
    const element = event.detail.elt;
    const trigger = event.detail.triggeringEvent;
    const submitter = trigger?.submitter || trigger?.target?.closest?.('button, input[type="submit"]');
    if (pending.has(element)) return;
    pending.add(element);
    confirm({title: event.detail.question}).then(accepted => {
      if (accepted && element.isConnected && !submitter?.disabled) {
        // HTMX tracks the submitter through focus; the modal temporarily blurs it.
        // Restore it before the continuation to retain name/value/form overrides.
        submitter?.focus({preventScroll: true});
        event.detail.issueRequest(true);
      }
    }).finally(() => pending.delete(element));
  });
  document.addEventListener('htmx:beforeRequest', event => {
    const form = event.detail.elt?.closest('form');
    if (!form || (event.detail.requestConfig?.verb || 'get').toLowerCase() === 'get') return;
    if (busy.has(form)) { event.preventDefault(); return; }
    lock(form);
    event.detail.xhr?.addEventListener('loadend', () => unlock(form), {once: true});
  });
  document.addEventListener('htmx:afterRequest', event => {
    const {xhr, elt} = event.detail;
    const form = elt?.closest('form');
    if (form) unlock(form);
    // HTTP 2xx alone is never proof of a successful business operation.
    if (!xhr || responseSeen.has(xhr) || !(event.detail.failed || xhr.status >= 400 || xhr.status === 0)) return;
    responseSeen.add(xhr);
    const text = xhr.status === 403 ? 'اجازه انجام این عملیات را ندارید.'
      : xhr.status === 404 ? 'مورد درخواستی در دسترس نیست.'
      : xhr.status === 409 ? 'وضعیت اطلاعات تغییر کرده است. صفحه را بازبینی کنید.'
      : [400, 422].includes(xhr.status) ? 'اطلاعات واردشده را بررسی کنید.'
      : 'دریافت پاسخ ممکن نشد. وضعیت اطلاعات را پیش از تلاش دوباره بررسی کنید.';
    notify('error', text);
  });
  document.addEventListener('htmx:afterSwap', () => consume());
  document.addEventListener('htmx:oobAfterSwap', () => consume());
  window.addEventListener('pageshow', reset);
  window.addEventListener('pagehide', reset);
  const mount = () => {
    consume();
    new MutationObserver(records => {
      if (records.some(record => [...record.addedNodes].some(node => node.nodeType === 1 &&
        (node.matches('[data-feedback-messages]') || node.querySelector('[data-feedback-messages]'))))) consume();
    }).observe(document.body, {childList: true, subtree: true});
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mount, {once: true});
  else mount();
})();
