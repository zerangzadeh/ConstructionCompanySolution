(() => {
  const group = document.querySelector('[data-rfq-supplier-search]');
  if (!group) return;

  const controls = group.querySelector('[data-supplier-search-control]');
  const search = controls.querySelector('input[type="search"]');
  const empty = controls.querySelector('[data-supplier-search-empty]');
  const normalize = (value) => value.trim().toLocaleLowerCase('fa')
    .replace(/ي/g, 'ی').replace(/ك/g, 'ک');
  const suppliers = [...group.querySelectorAll('input[name="supplier_ids"]')].map((input) => {
    const label = input.closest('label');
    return { input, label, name: normalize(label.textContent) };
  });

  if (!suppliers.length) return;
  controls.hidden = false;
  const filter = () => {
    const query = normalize(search.value);
    for (const supplier of suppliers) {
      supplier.label.hidden = !supplier.input.checked && !supplier.name.includes(query);
    }
    empty.hidden = suppliers.some((supplier) => supplier.name.includes(query));
  };
  search.addEventListener('input', filter);
  group.addEventListener('change', filter);
})();
