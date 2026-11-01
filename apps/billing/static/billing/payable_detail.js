/* Presentation only: native dialogs preserve focus, Escape, and modal semantics. */
(() => {
  const sectionLinks = [...document.querySelectorAll('.pc-sections a[href^="#"]')];
  const selectSection = selected => {
    sectionLinks.forEach(link => {
      if (link === selected) link.setAttribute('aria-current', 'location');
      else link.removeAttribute('aria-current');
    });
  };
  const updateActiveSection = () => selectSection(
    sectionLinks.find(link => link.hash === window.location.hash) || sectionLinks[0]
  );
  sectionLinks.forEach(link => {
    link.addEventListener('click', () => selectSection(link));
  });
  window.addEventListener('hashchange', updateActiveSection);
  updateActiveSection();

  document.querySelectorAll('[data-pc-open]').forEach(button => {
    button.addEventListener('click', () => {
      const dialog = document.getElementById(button.dataset.pcOpen);
      if (!dialog) return;
      dialog.showModal();
      dialog.addEventListener('close', () => button.focus(), {once: true});
    });
  });
  document.querySelectorAll('[data-pc-close]').forEach(button => {
    button.addEventListener('click', () => button.closest('dialog').close());
  });
})();
