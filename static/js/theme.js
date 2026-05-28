(function () {
  var STORAGE_KEY = "taskun-theme";

  function getStored() {
    try {
      return localStorage.getItem(STORAGE_KEY);
    } catch (e) {
      return null;
    }
  }

  function setStored(mode) {
    try {
      localStorage.setItem(STORAGE_KEY, mode);
    } catch (e) {}
  }

  function applyMeta(mode) {
    var cs = document.getElementById("meta-color-scheme");
    var tc = document.getElementById("meta-theme-color");
    if (cs) {
      cs.setAttribute("content", mode === "dark" ? "dark" : "light");
    }
    if (tc) {
      tc.setAttribute("content", mode === "dark" ? "#111827" : "#fafbfc");
    }
  }

  function syncToggleButtons(mode) {
    var dark = mode === "dark";
    document.querySelectorAll(".theme-toggle").forEach(function (btn) {
      btn.setAttribute("aria-pressed", dark ? "true" : "false");
      btn.setAttribute(
        "aria-label",
        dark ? "Включить светлую тему" : "Включить тёмную тему"
      );
    });
  }

  function setTheme(mode) {
    if (mode !== "dark" && mode !== "light") {
      mode = "light";
    }
    document.documentElement.setAttribute("data-theme", mode);
    setStored(mode);
    applyMeta(mode);
    syncToggleButtons(mode);
  }

  window.taskunSetTheme = setTheme;

  (function syncFromDom() {
    var cur = document.documentElement.getAttribute("data-theme") || "light";
    applyMeta(cur === "dark" ? "dark" : "light");
  })();

  document.addEventListener("DOMContentLoaded", function () {
    var stored = getStored();
    var initial = stored === "dark" || stored === "light" ? stored : "light";
    setTheme(initial);

    document.querySelectorAll(".theme-toggle").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var cur = document.documentElement.getAttribute("data-theme") || "light";
        setTheme(cur === "dark" ? "light" : "dark");
      });
    });
  });
})();
