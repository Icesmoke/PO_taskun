/**
 * Календарь для полей даты (Flatpickr, формат dd.mm.YYYY).
 * Разметка: <input class="js-date" …>
 *
 * Внутри <dialog> календарь монтируется в dialog и позиционируется
 * относительно поля ввода (getBoundingClientRect), иначе Flatpickr
 * ставит его «куда попало» из‑за другой системы координат.
 */
(function () {
  var DATE_FMT = "d.m.Y";
  var GAP = 4;

  function normalizeDateStr(value) {
    var v = value == null ? "" : String(value).trim();
    if (!v) return "";
    var m = v.match(/^(\d{2})[.\-](\d{2})[.\-](\d{4})$/);
    if (m) return m[1] + "." + m[2] + "." + m[3];
    return v;
  }

  function positionNearInput(instance) {
    var el = instance.element;
    var cal = instance.calendarContainer;
    if (!el || !cal) return;

    var dlg = el.closest && el.closest("dialog");
    if (!dlg) return;

    // Диалог — containing block для absolute-календаря
    if (window.getComputedStyle(dlg).position === "static") {
      dlg.style.position = "relative";
    }

    var elRect = el.getBoundingClientRect();
    var dlgRect = dlg.getBoundingClientRect();
    var calH = cal.offsetHeight || 300;
    var calW = cal.offsetWidth || 307;

    var left = elRect.left - dlgRect.left;
    var topBelow = elRect.bottom - dlgRect.top + GAP;
    var topAbove = elRect.top - dlgRect.top - calH - GAP;

    // Если снизу не хватает места — открываем вверх
    var spaceBelow = dlgRect.bottom - elRect.bottom;
    var top = spaceBelow < calH + GAP && topAbove > 0 ? topAbove : topBelow;

    // Не вылезать за правый край диалога
    var maxLeft = Math.max(0, dlgRect.width - calW - 8);
    if (left > maxLeft) left = maxLeft;
    if (left < 0) left = 0;

    cal.style.position = "absolute";
    cal.style.left = Math.round(left) + "px";
    cal.style.top = Math.round(top) + "px";
    cal.style.right = "auto";
    cal.style.bottom = "auto";
    cal.style.margin = "0";
    cal.style.transform = "none";
    cal.style.zIndex = "10050";
  }

  function optionsFor(el) {
    var opts = {
      dateFormat: DATE_FMT,
      allowInput: true,
      disableMobile: true,
      allowInvalidPreload: true,
      // Отключаем автопозиционирование Flatpickr — ставим сами у поля
      position: "auto",
      onReady: function (_d, _s, instance) {
        positionNearInput(instance);
      },
      onOpen: function (_d, _s, instance) {
        // Два кадра: после раскладки Flatpickr и после измерения высоты календаря
        positionNearInput(instance);
        window.requestAnimationFrame(function () {
          positionNearInput(instance);
        });
      },
    };
    if (typeof flatpickr !== "undefined" && flatpickr.l10ns && flatpickr.l10ns.ru) {
      opts.locale = flatpickr.l10ns.ru;
    }
    var dlg = el.closest && el.closest("dialog");
    if (dlg) opts.appendTo = dlg;
    return opts;
  }

  function destroyOne(el) {
    if (el && el._flatpickr) {
      try {
        el._flatpickr.destroy();
      } catch (e) {
        /* ignore */
      }
    }
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

  function dateInputs(root) {
    var scope = root && root.querySelectorAll ? root : document;
    return scope.querySelectorAll("input.js-date");
  }

  function initDatePickers(root) {
    if (typeof flatpickr === "undefined") return;
    dateInputs(root).forEach(function (el) {
      initOne(el);
    });
  }

  /** Пересоздать календари (нужно после открытия <dialog>). */
  function reinitDatePickers(root) {
    if (typeof flatpickr === "undefined") return;
    dateInputs(root).forEach(function (el) {
      var val = el.value;
      destroyOne(el);
      el.value = normalizeDateStr(val);
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
  window.reinitDatePickers = reinitDatePickers;
  window.setDateInput = setDateInput;

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      initDatePickers(document);
    });
  } else {
    initDatePickers(document);
  }
})();
