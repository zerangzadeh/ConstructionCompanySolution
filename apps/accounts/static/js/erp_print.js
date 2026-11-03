"use strict";
document.querySelector("[data-print-document]")?.addEventListener("click", async () => {
  await document.fonts.ready;
  window.print();
});
