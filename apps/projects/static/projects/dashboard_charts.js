/* Chart presentation only. Django owns scoped data, Decimal values and labels. */
(() => {
    'use strict';
    const format = value => {
        const [whole, fraction] = String(value).split('.');
        const number = new Intl.NumberFormat('fa-IR').format(BigInt(whole));
        return number + (fraction && /[1-9]/.test(fraction) ? '٫' + fraction.replace(/[0-9]/g, d => '۰۱۲۳۴۵۶۷۸۹'[d]) : '');
    };
    const mount = () => {
        const source = document.getElementById('project-dashboard-data');
        if (!source || typeof Chart !== 'function') return;
        const styles = getComputedStyle(document.documentElement);
        const color = token => styles.getPropertyValue('--bonira-' + token).trim();
        const palette = ['royal-blue', 'deep-navy', 'muted', 'light-gray'].map(color);
        let configs;
        try { configs = JSON.parse(source.textContent); } catch { return; }
        for (const config of configs) {
            const canvas = document.getElementById(config.id);
            if (!canvas || Chart.getChart(canvas) || !config.rows.length) continue;
            const container = canvas.parentElement;
            try {
                canvas.hidden = false;
                container.dataset.chartReady = 'true';
                new Chart(canvas, {
                    type: config.type,
                    data: {
                        labels: config.rows.map(row => row.label),
                        datasets: [{
                            label: config.unit,
                            data: config.rows.map(row => Number(row.value)),
                            backgroundColor: palette,
                            borderWidth: 0,
                            borderRadius: config.type === 'bar' ? 5 : 0,
                            maxBarThickness: 36,
                        }],
                    },
                    options: {
                        responsive: true, maintainAspectRatio: false, animation: false,
                        locale: 'fa-IR',
                        font: {family: 'Vazirmatn'},
                        cutout: config.type === 'doughnut' ? '72%' : undefined,
                        plugins: {
                            legend: {display: false},
                            tooltip: {
                                rtl: true, textDirection: 'rtl',
                                titleFont: {family: 'Vazirmatn'}, bodyFont: {family: 'Vazirmatn'},
                                callbacks: {label: ctx => config.rows[ctx.dataIndex].label + ': ' + format(config.rows[ctx.dataIndex].value) + ' ' + config.unit},
                            },
                        },
                        scales: config.type === 'bar' ? {
                            x: {grid: {display: false}, ticks: {color: color('slate'), font: {family: 'Vazirmatn', size: 11}}},
                            y: {beginAtZero: true, ticks: {color: color('muted'), font: {family: 'Vazirmatn', size: 10}, callback: value => new Intl.NumberFormat('fa-IR', {notation: 'compact'}).format(value)}, grid: {color: color('light-gray')}},
                        } : undefined,
                    },
                });
            } catch {
                Chart.getChart(canvas)?.destroy();
                canvas.hidden = true;
                delete container.dataset.chartReady;
                // Exact, accessible server-rendered values remain available.
            }
        }
    };
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mount);
    else mount();
    document.addEventListener('htmx:afterSwap', mount);
})();
