/**
 * Календарь для полей даты (Flatpickr, формат dd.mm.YYYY).
 * Разметка: <input class="js-date" …>
 */
(function () {
  var DATE_FMT = "d.m.Y";

  function normalizeDateStr(value) {
    var v = value == null ? "" : String(value).trim();
    if (!v) return "";
    var m = v.match(/^(\d{2})[.\-](\d{2})[.\-](\d{4})$/);
    if (m) return m[1] + "." + m[2] + "." + m[3];
    return v;
  }

  function options() {
    var opts = {
      dateFormat: DATE_FMT,
      allowInput: true,
      disableMobile: true,
      allowInvalidPreload: true,
    };
    if (typeof flatpickr !== "undefined" && flatpickr.l10ns && flatpickr.l10ns.ru) {
      opts.locale = flatpickr.l10ns.ru;
    }
    return opts;
  }

  function optionsFor(el) {
    var opts = options();
    var dlg = el.closest && el.closest("dialog");
    if (dlg) opts.appendTo = dlg;
    return opts;
  }

  function initOne(el) {
    if (!el || el.nodeName !== "INPUT") return null;
    if (typeof flatpickr === "undefined") return null;
    if (el._flatpickr) return el._flatpickr;
    el.classList.add("js-date");
    el.setAttribute("autocomplete", "off");
    if (!el.getAttribute("placeholder")) {
      el.setAttribute("placeholder", "dd.mm.YYYY");
    }
    var normalized = normalizeDateStr(el.value);
    if (normalized !== el.value) el.value = normalized;
    return flatpickr(el, optionsFor(el));
  }

  function initDatePickers(root) {
    if (typeof flatpickr === "undefined") return;
    var scope = root && root.querySelectorAll ? root : document;
    scope.querySelectorAll("input.js-date").forEach(function (el) {
      initOne(el);
    });
  }

  function setDateInput(el, value) {
    if (!el) return;
    var v = normalizeDateStr(value);
    if (el._flatpickr) {
      if (v) el._flatpickr.setDate(v, false, DATE_FMT);
      else el._flatpickr.clear();
      return;
    }
    el.value = v;
    initOne(el);
    if (el._flatpickr && v) el._flatpickr.setDate(v, false, DATE_FMT);
  }

  window.initDatePickers = initDatePickers;
  window.setDateInput = setDateInput;

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      initDatePickers(document);
    });
  } else {
    initDatePickers(document);
  }
})();
