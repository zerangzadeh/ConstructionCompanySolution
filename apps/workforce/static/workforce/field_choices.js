/* Progressive enhancement of native Django selects. Server scope is authoritative. */
(() => {
  'use strict';
  if (!window.TomSelect || window.BoniraFieldChoices) return;
  window.BoniraFieldChoices = true;
  TomSelect.define('virtual_scroll', window.virtual_scroll);
  const controls = root => [...root.querySelectorAll('select[data-business-choice]')];
  const parent = (select, name) => [...(select.form?.elements || [])].find(el => el.name === name);
  const endpoint = (select, query) => {
    const url = new URL(select.dataset.optionsUrl, location.origin);
    url.searchParams.set('q', query);
    // Explicitly replace previous journey context, including values cleared by the user.
    for (const name of new Set(['project', 'site', 'calendar', ...(select.dataset.choiceParents || '').split(' ').filter(Boolean)])) {
      const field = parent(select, name);
      if (field) {
        url.searchParams.delete(name);
        if (field !== select && field.value) url.searchParams.set(name, field.value);
      }
    }
    if (select.dataset.choicePurpose) url.searchParams.set('purpose', select.dataset.choicePurpose);
    return url.href;
  };
  const normalize = value => value.toLowerCase().replace(/[۰-۹]/g, d => '۰۱۲۳۴۵۶۷۸۹'.indexOf(d)).replace(/[٠-٩]/g, d => '٠١٢٣٤٥٦٧٨٩'.indexOf(d)).replace(/ي/g, 'ی').replace(/ك/g, 'ک').replace(/[\u064b-\u065f]/g, '');
  function mount(root = document) {
    for (const select of controls(root)) {
      if (select.tomselect) continue;
      const status = select.closest('[data-field-search]').querySelector('[data-choice-status]');
      let generation = 0, pending;
      const message = text => { status.textContent = text; };
      const nativeClasses = [...select.classList];
      const displayChoice = (data, escape) => {
        if (select.dataset.businessNamesPrimary !== 'true') return '<div>' + escape(data.label) + '</div>';
        const [name, ...details] = data.label.split(' · ');
        return '<div><span class="business-choice-name">' + escape(name) + '</span>' +
          (details.length ? '<span class="business-choice-code" dir="auto">' + escape(details.join(' · ')) + '</span>' : '') + '</div>';
      };
      const widget = new TomSelect(select, {
        plugins: ['virtual_scroll'], valueField: 'value', labelField: 'label', searchField: ['label'],
        create: false, maxItems: 1, maxOptions: null, loadThrottle: 250,
        preload: 'focus', placeholder: select.dataset.placeholder,
        // Exclude non-matching HTML fallback options retained by virtual_scroll.
        score: query => {const terms = normalize(query).split(/\s+/).filter(Boolean); return item => terms.every(term => normalize(item.label).includes(term)) ? 1 : 0;},
        firstUrl: query => endpoint(select, query),
        load: function(query, callback) {
          pending?.abort();
          const controller = new AbortController();
          pending = controller;
          const version = generation;
          this.boniraFailed = false;
          message('در حال جست‌وجو…');
          fetch(this.getUrl(query), {credentials: 'same-origin', headers: {Accept: 'application/json'}, signal: controller.signal})
            .then(response => {if (!response.ok) throw new Error('unavailable'); return response.json();})
            .then(data => {
              if (version !== generation || controller.signal.aborted) {callback(); return;}
              this.setNextUrl(query, data.next ? new URL(data.next, location.origin).href : false);
              callback(data.results);
              message(data.results.length ? 'گزینه‌ها آماده انتخاب هستند.' : 'گزینه‌ای یافت نشد.');
            }).catch(error => {
              if (error.name !== 'AbortError' && version === generation) {
                this.boniraFailed = true;
                delete this.loadedSearches[query];
                message('دریافت گزینه‌ها انجام نشد؛ دوباره تلاش کنید.');
              }
              callback();
              // A failed remote lookup must remain visible even when native
              // fallback options happen to match the query.
              if (this.boniraFailed && version === generation && !this.dropdown.querySelector('[data-choice-retry]')) {
                const notice = document.createElement('div');
                notice.className = 'no-results';
                notice.innerHTML = 'دریافت گزینه‌ها انجام نشد. <button type="button" data-choice-retry>تلاش دوباره</button>';
                this.dropdown_content.prepend(notice);
              }
            });
        },
        render: {
          option: displayChoice,
          item: displayChoice,
          no_results: function() {
            return this.boniraFailed
              ? '<div class="no-results">دریافت گزینه‌ها انجام نشد. <button type="button" data-choice-retry>تلاش دوباره</button></div>'
              : '<div class="no-results">گزینه‌ای یافت نشد.</div>';
          },
          loading: () => '<div class="spinner">در حال جست‌وجو…</div>',
          loading_more: () => '<div class="loading-more-results">در حال دریافت گزینه‌ها…</div>',
          no_more_results: () => '<div class="no-more-results">پایان فهرست</div>',
        },
        onInitialize: function() {
          this.control_input.setAttribute('aria-label', select.dataset.placeholder);
          for (const attr of ['aria-describedby', 'aria-invalid']) {
            if (select.hasAttribute(attr)) this.control_input.setAttribute(attr, select.getAttribute(attr));
          }
        },
      });
      widget.wrapper.classList.remove(...nativeClasses);
      const reset = () => {
        generation++;
        pending?.abort();
        widget.clear(true);
        widget.clearOptions();
        widget.clearPagination();
        widget.loadedSearches = {};
        widget.setTextboxValue('');
        const first = select.dataset.dependsOn?.split(' ')[0];
        const blocked = (select.dataset.requiresParent === 'true' || ['site', 'activity', 'shift'].includes(select.dataset.businessChoice)) && first && !parent(select, first)?.value;
        blocked ? widget.disable() : widget.enable();
        message(blocked ? 'ابتدا گزینه بالادست را انتخاب کنید.' : 'فهرست به‌روز شد؛ دوباره انتخاب کنید.');
      };
      const dependencies = select.dataset.dependsOn?.split(' ').filter(Boolean) || [];
      for (const name of dependencies) parent(select, name)?.addEventListener('change', reset);
      const requiredParent = dependencies[0];
      if ((select.dataset.requiresParent === 'true' || ['site', 'activity', 'shift'].includes(select.dataset.businessChoice)) && requiredParent && !parent(select, requiredParent)?.value) widget.disable();
      select.closest('[data-field-search]').addEventListener('click', event => {
        if (event.target.closest('[data-choice-retry]')) {
          widget.loadedSearches = {};
          widget.clearPagination();
          widget.load(widget.control_input.value);
        }
      });
      widget.on('destroy', () => {generation++; pending?.abort(); for (const name of dependencies) parent(select, name)?.removeEventListener('change', reset);});
    }
  }
  document.addEventListener('htmx:beforeCleanupElement', event => {
    const target = event.detail.elt;
    if (target.matches?.('select[data-business-choice]')) target.tomselect?.destroy();
    for (const select of controls(target)) select.tomselect?.destroy();
  });
  document.addEventListener('htmx:afterSwap', () => mount());
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => mount());
  else mount();
})();
