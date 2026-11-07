const category = document.querySelector('[data-leave-category]');
if (category?.form?.elements.kind) {
  const kind = category.form.elements.kind;
  const syncList = () => {
    if (kind.value === 'leave') category.setAttribute('list', 'timekeeping-leave-categories');
    else category.removeAttribute('list');
  };
  syncList();
  kind.addEventListener('change', syncList);
}
