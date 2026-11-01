/* Presentation only. All money and proportions are resolved on the server. */
(() => {
    const mount = () => {
        const navigation = document.querySelector('.cd-journey');
        const updateNavigation = () => {
            const hash = location.hash || '#overview';
            navigation?.querySelectorAll('a[href^="#"]').forEach(link => {
                const current = link.getAttribute('href') === hash;
                link.classList.toggle('is-current', current);
                if (current) link.setAttribute('aria-current', 'location'); else link.removeAttribute('aria-current');
            });
            const details = document.getElementById(hash.slice(1));
            if (details?.tagName === 'DETAILS') details.open = true;
        };
        updateNavigation();
        window.addEventListener('hashchange', updateNavigation);
        const source = document.getElementById('contract-financial-data');
        const canvas = document.getElementById('contract-financial-chart');
        if (!source || !canvas || typeof Chart !== 'function') return;
        const rows = JSON.parse(source.textContent);
        const styles = getComputedStyle(document.documentElement);
        const blue = styles.getPropertyValue('--bonira-royal-blue').trim();
        canvas.hidden = false;
        try {
            new Chart(canvas, {
                type: 'bar',
                plugins: [{id: 'serverPercentLabels', afterDatasetsDraw(chart) {
                    const ctx = chart.ctx;
                    ctx.save(); ctx.font = '600 12px Vazirmatn'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
                    rows.forEach((row, index) => {
                        const bar = chart.getDatasetMeta(index).data[0];
                        if (bar && bar.width > 45) {
                            ctx.fillStyle = styles.getPropertyValue(index === 0 ? '--bonira-white' : '--bonira-ink').trim();
                            ctx.fillText(row.percent.replace(/[0-9]/g, n => '۰۱۲۳۴۵۶۷۸۹'[n]) + '٪', (bar.x + bar.base) / 2, bar.y);
                        }
                    });
                    ctx.restore();
                }}],
                data: { labels: ['مبلغ مؤثر قرارداد'], datasets: rows.map((row, index) => ({
                    label: row.label, data: [Number(row.value)],
                    backgroundColor: [blue, blue + '70', styles.getPropertyValue('--bonira-light-gray').trim()][index],
                    borderWidth: 0, barThickness: 29,
                })) },
                options: {
                    indexAxis: 'y', responsive: true, maintainAspectRatio: false, animation: false,
                    scales: { x: {stacked: true, display: false}, y: {stacked: true, display: false} },
                    plugins: {legend: {display: false}, tooltip: {
                        rtl: true, textDirection: 'rtl', bodyFont: {family: 'Vazirmatn'},
                        callbacks: {label: context => {
                            const row = rows[context.datasetIndex];
                            return row.label + ': ' + row.formatted;
                        }},
                    }},
                },
            });
            canvas.parentElement.dataset.chartReady = 'true';
        } catch { canvas.hidden = true; }
    };
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mount); else mount();
})();
