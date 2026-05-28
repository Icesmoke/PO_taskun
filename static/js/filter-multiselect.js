/**
 * Улучшенный множественный выбор фильтров (Tom Select).
 */
(function () {
  function init() {
    if (typeof TomSelect === "undefined") return;
    document.querySelectorAll("select.js-filter-multiselect").forEach(function (el) {
      if (el.dataset.tsInited === "1") return;
      el.dataset.tsInited = "1";
      new TomSelect(el, {
        plugins: ["remove_button"],
        persist: false,
        create: false,
        maxItems: null,
        placeholder: el.getAttribute("data-placeholder") || "Выберите…",
        hideSelected: false,
        closeAfterSelect: false,
      });
    });
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
