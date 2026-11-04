/* Presentation lifecycle only: never intercept fetch/XHR or change request behavior. */
(() => {
    'use strict';
    const element = document.querySelector('[data-global-loading-bar]');
    if (!element || window.BoniraLoading) return;
    const bar = element.firstElementChild;
    const status = document.querySelector('[data-global-loading-status]');
    const active = new Map();
    let delay, completion, navigation;
    let failed = false;
    const reducedMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    function hide() {
        clearTimeout(delay);
        clearTimeout(completion);
        delay = completion = undefined;
        element.hidden = true;
        if (status) status.textContent = '';
        element.removeAttribute('aria-valuenow');
        delete element.dataset.state;
        bar.style.removeProperty('transform');
    }

    function render() {
        // Concurrent operations have no reliable common denominator.
        const value = active.size === 1 ? active.values().next().value.value : null;
        const known = Number.isFinite(value);
        element.dataset.mode = known ? 'determinate' : 'indeterminate';
        if (known) {
            element.setAttribute('aria-valuenow', String(value));
            bar.style.transform = `scaleX(${value / 100})`;
        } else {
            element.removeAttribute('aria-valuenow');
            bar.style.removeProperty('transform');
        }
    }

    function reset() {
        for (const task of [...active.values()]) task.cancel();
        navigation = undefined;
        hide();
    }

    function start({signal, timeoutMs = 120000} = {}) {
        const key = Symbol();
        let timer;
        const task = {
            value: null,
            progress(value) {
                if (!active.has(key) || !Number.isFinite(value) || value < 0 || value > 100) return;
                task.value = value;
                armTimeout();
                render();
            },
            finish({failed: error = false} = {}) {
                if (!active.delete(key)) return;
                clearTimeout(timer);
                signal?.removeEventListener('abort', task.cancel);
                failed ||= error;
                if (active.size) { render(); return; }
                clearTimeout(delay);
                delay = undefined;
                if (element.hidden || failed || reducedMotion()) { hide(); return; }
                element.removeAttribute('aria-valuenow');
                element.dataset.state = 'complete';
                completion = setTimeout(hide, 180);
            },
            cancel() { task.finish({failed: true}); },
        };
        function armTimeout() {
            clearTimeout(timer);
            // A missing completion event cannot leave the shell busy forever.
            timer = setTimeout(task.cancel, Math.max(1000, Number(timeoutMs) || 120000));
        }
        if (signal?.aborted) return task;
        if (!active.size) {
            hide();
            failed = false;
            delay = setTimeout(() => {
                delay = undefined;
                if (active.size) {
                    render();
                    element.hidden = false;
                    if (status) status.textContent = element.getAttribute('aria-label');
                }
            }, 250);
        }
        active.set(key, task);
        signal?.addEventListener('abort', task.cancel, {once: true});
        armTimeout();
        render();
        return task;
    }
    // Explicit opt-in for primary-content async work; call finish in finally,
    // cancel on failure, and progress only with a trustworthy percentage.
    window.BoniraLoading = Object.freeze({start, reset});

    function beginNavigation(signal) {
        navigation?.cancel();
        navigation = start({signal});
    }
    const optedOut = node => node?.closest?.('[data-global-loading="false"]');
    if (window.navigation) {
        window.navigation.addEventListener('navigate', event => {
            if (event.hashChange || event.downloadRequest !== null || event.destination.sameDocument || optedOut(event.sourceElement)) return;
            // Wait for other listeners (including navigation guards) to cancel.
            queueMicrotask(() => { if (!event.defaultPrevented) beginNavigation(event.signal); });
        });
        window.navigation.addEventListener('navigatesuccess', () => navigation?.finish());
        window.navigation.addEventListener('navigateerror', () => navigation?.cancel());
    } else {
        // Best-effort fallback: observe only uncancelled same-window navigation.
        window.addEventListener('click', event => {
            const link = event.target.closest?.('a[href]');
            if (!link || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey ||
                link.hasAttribute('download') || optedOut(link)) return;
            const target = link.target || document.querySelector('base')?.target;
            if (target && target !== '_self') return;
            const url = new URL(link.href, location.href);
            if (!['http:', 'https:'].includes(url.protocol) ||
                (url.origin === location.origin && url.pathname === location.pathname && url.search === location.search && url.hash)) return;
            queueMicrotask(() => { if (!event.defaultPrevented) beginNavigation(); });
        });
        window.addEventListener('submit', event => {
            const form = event.target;
            const target = event.submitter?.formTarget || form.target || document.querySelector('base')?.target;
            const method = event.submitter?.getAttribute('formmethod') || form.method;
            if (method === 'dialog' || (target && target !== '_self') || optedOut(form)) return;
            queueMicrotask(() => { if (!event.defaultPrevented) beginNavigation(); });
        });
    }

    const requests = new WeakMap();
    document.addEventListener('htmx:beforeSend', event => {
        const {xhr, target, elt} = event.detail;
        if (!xhr || requests.has(xhr) || optedOut(elt) || optedOut(target)) return;
        const main = document.getElementById('main-content');
        const explicit = elt?.closest?.('[data-global-loading="true"]');
        if (!explicit && !(main && (target === main || target?.contains(main)))) return;
        const task = start();
        requests.set(xhr, task);
        // Native loadend also fires for errors/aborts and detached HTMX sources.
        xhr.addEventListener('loadend', () => {
            task.finish({failed: xhr.status === 0 || xhr.status >= 400});
            requests.delete(xhr);
        }, {once: true});
    });
    document.addEventListener('htmx:afterRequest', event => {
        const {xhr, failed} = event.detail;
        requests.get(xhr)?.finish({failed: Boolean(failed)});
        requests.delete(xhr);
    });
    window.addEventListener('pagehide', reset);
    window.addEventListener('pageshow', reset);
    window.addEventListener('popstate', reset);
    window.addEventListener('load', () => navigation?.finish(), {once: true});
})();
