/* Progressive enhancement of native Django selects. Server scope is authoritative. */
(() => {
  'use strict';
  if (!window.TomSelect || window.BoniraFieldChoices) return;
  window.BoniraFieldChoices = true;
  TomSelect.define('virtual_scroll', window.virtual_scroll);
  const controls = root => [
    ...(root.matches?.('select[data-business-choice], input[data-editable-text-choice="true"]') ? [root] : []),
    ...root.querySelectorAll('select[data-business-choice], input[data-editable-text-choice="true"]'),
  ];
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
      const container = select.closest('[data-field-search]');
      const status = container.querySelector('[data-choice-status]');
      const local = select.dataset.localChoices === 'true';
      const editableText = local && select.matches('input[data-editable-text-choice="true"]');
      const initiallyDisabled = select.disabled;
      let generation = 0, pending;
      const message = (text, visible = false, action = null) => {
        status.textContent = text;
        if (action) {
          const link = document.createElement('a');
          link.href = action.url;
          link.className = 'font-semibold text-blue-700 underline';
          link.textContent = action.label;
          status.append(' ', link);
        }
        status.classList.toggle('sr-only', !visible);
      };
      const emptyMessage = query => !query && select.dataset.emptyChoices || 'گزینه‌ای یافت نشد.';
      const nativeClasses = [...select.classList];
      const displayChoice = (data, escape) => {
        if (select.dataset.businessNamesPrimary !== 'true') return '<div>' + escape(data.label) + '</div>';
        const [name, ...details] = data.label.split(' · ');
        return '<div><span class="business-choice-name">' + escape(name) + '</span>' +
          (details.length ? '<span class="business-choice-code" dir="auto">' + escape(details.join(' · ')) + '</span>' : '') + '</div>';
      };
      const widget = new TomSelect(select, {
        plugins: local ? [] : ['virtual_scroll'], valueField: 'value', labelField: 'label', searchField: ['label'],
        create: editableText ? value => ({value:value.trim(), label:value.trim()}) : false,
        createFilter: editableText ? value => !!value.trim() && (select.maxLength < 0 || value.trim().length <= select.maxLength) : null,
        ...(editableText ? {
          options:[...new Set([...select.list.options].map(option=>option.value).concat(select.value || []))].filter(Boolean).map(value=>({value,label:value})),
          items:select.value ? [select.value] : [],
        } : {}),
        maxItems: select.multiple ? null : 1, maxOptions: null, loadThrottle: 250,
        allowEmptyOption: local, preload: local ? false : 'focus', placeholder: select.dataset.placeholder,
        // Exclude non-matching HTML fallback options retained by virtual_scroll.
        score: query => {const terms = normalize(query).split(/\s+/).filter(Boolean); return item => terms.every(term => normalize(item.label).includes(term)) ? 1 : 0;},
        firstUrl: query => endpoint(select, query),
        load: local ? null : function(query, callback) {
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
              const empty = data.results.length === 0;
              message(empty ? emptyMessage(query) : 'گزینه‌ها آماده انتخاب هستند.',
                empty && !query && !!select.dataset.emptyChoices,
                empty && !query ? data.empty_action : null);
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
          option_create: (data, escape) => '<div class="create">انتخاب دسته جدید: ' + escape(data.input) + '</div>',
          option: displayChoice,
          item: displayChoice,
          no_results: function(data, escape) {
            return this.boniraFailed
              ? '<div class="no-results">دریافت گزینه‌ها انجام نشد. <button type="button" data-choice-retry>تلاش دوباره</button></div>'
              : '<div class="no-results">' + escape(emptyMessage(data?.input)) + '</div>';
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
        (initiallyDisabled || blocked) ? widget.disable() : widget.enable();
        message(blocked ? 'ابتدا گزینه بالادست را انتخاب کنید.' : 'فهرست به‌روز شد؛ دوباره انتخاب کنید.');
      };
      const dependencies = select.dataset.dependsOn?.split(' ').filter(Boolean) || [];
      for (const name of dependencies) parent(select, name)?.addEventListener('change', reset);
      const requiredParent = dependencies[0];
      if ((select.dataset.requiresParent === 'true' || ['site', 'activity', 'shift'].includes(select.dataset.businessChoice)) && requiredParent && !parent(select, requiredParent)?.value) widget.disable();
      const retry = event => {
        if (event.target.closest('[data-choice-retry]')) {
          widget.loadedSearches = {};
          widget.clearPagination();
          widget.load(widget.control_input.value);
        }
      };
      container.addEventListener('click', retry);
      widget.on('destroy', () => {
        generation++; pending?.abort();
        // Tom Select may have disabled the native select for a missing parent.
        // Restore its configured state before a later HTMX mount.
        select.disabled = initiallyDisabled;
        container.removeEventListener('click', retry);
        for (const name of dependencies) parent(select, name)?.removeEventListener('change', reset);
      });
    }
  }
  document.addEventListener('htmx:beforeCleanupElement', event => {
    const target = event.detail.elt;
    for (const select of controls(target)) select.tomselect?.destroy();
  });
  document.addEventListener('htmx:afterSwap', () => mount());
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => mount());
  else mount();
})();
