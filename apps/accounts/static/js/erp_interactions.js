/* Opt-in presentation only. Existing forms/endpoints own validation and mutations. */
(() => {
  'use strict';
  if (window.BoniraInteractions) return;
  window.BoniraInteractions = true;
  const pending = new WeakSet();
  const confirmed = new WeakSet();
  const options = {
    customClass: {popup: 'erp-interaction-popup', confirmButton: 'erp-btn erp-btn--primary', cancelButton: 'erp-btn erp-btn--secondary'},
    buttonsStyling: false,
    confirmButtonText: 'تأیید و ادامه', cancelButtonText: 'انصراف',
    showCancelButton: true, focusCancel: true, returnFocus: true,
    heightAuto: false,
  };
  document.addEventListener('submit', async event => {
    const form = event.target;
    const submitter = event.submitter;
    if (!form.matches('form[data-confirm-title]')) return;
    if (confirmed.has(form)) { confirmed.delete(form); return; }
    if (event.defaultPrevented) return;
    event.preventDefault();
    // Defer existing submit/HTMX handlers until the confirmed native submit event.
    event.stopImmediatePropagation();
    if (pending.has(form)) return;
    pending.add(form);
    try {
      const title = form.dataset.confirmTitle;
      const text = form.dataset.confirmText || '';
      const result = window.Swal
        ? await Swal.fire({...options, titleText: title, text,
          confirmButtonText: form.dataset.confirmLabel || options.confirmButtonText})
        : {isConfirmed: window.confirm(title + '\n' + text)};
      if (!result.isConfirmed || !form.isConnected || submitter?.disabled) return;
      confirmed.add(form);
      // Preserve submitter name/value, formaction, validation and existing events.
      try { form.requestSubmit(submitter || undefined); }
      finally { confirmed.delete(form); }
    } finally { pending.delete(form); }
  }, true);

  function feedback() {
    // Explicit page opt-in; never consume validation, warnings or arbitrary errors.
    if (!window.Swal || !document.querySelector('[data-success-toast]')) return;
    for (const message of document.querySelectorAll('.erp-message--success:not([data-toasted])')) {
      message.dataset.toasted = 'true';
      Swal.fire({toast: true, position: 'top-start', icon: 'success',
        titleText: message.textContent.trim().replace(/^✓\s*/, ''),
        showConfirmButton: false, showCloseButton: true, closeButtonAriaLabel: 'بستن پیام',
        timer: 5000, timerProgressBar: true, heightAuto: false,
        customClass: {popup: 'erp-interaction-popup'},
        didOpen: toast => {
          toast.addEventListener('mouseenter', Swal.stopTimer);
          toast.addEventListener('mouseleave', Swal.resumeTimer);
          toast.addEventListener('focusin', Swal.stopTimer);
          toast.addEventListener('focusout', Swal.resumeTimer);
        }});
      // Keep the server feedback readable after the transient toast disappears.
    }
  }
  document.addEventListener('htmx:afterSwap', feedback);
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', feedback, {once: true});
  else feedback();
})();
