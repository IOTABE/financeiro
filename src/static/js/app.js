(function () {
  "use strict";

  var root = document.documentElement;
  var STORAGE_KEY = "clareza-theme";

  function systemTheme() {
    return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches
      ? "dark"
      : "light";
  }

  function applyTheme(theme) {
    root.dataset.theme = theme;
    try {
      localStorage.setItem(STORAGE_KEY, theme);
    } catch (error) {}
    var button = document.querySelector("[data-theme-toggle]");
    if (button) {
      button.setAttribute(
        "aria-label",
        theme === "dark" ? "Mudar para tema claro" : "Mudar para tema escuro"
      );
    }
  }

  function currentTheme() {
    var stored = root.dataset.theme || "system";
    if (stored === "system") {
      return systemTheme();
    }
    return stored;
  }

  var toggle = document.querySelector("[data-theme-toggle]");
  if (toggle) {
    var button = toggle;
    button.setAttribute(
      "aria-label",
      currentTheme() === "dark" ? "Mudar para tema claro" : "Mudar para tema escuro"
    );
    button.addEventListener("click", function () {
      applyTheme(currentTheme() === "dark" ? "light" : "dark");
    });
  }

  document.querySelectorAll("[data-dismiss]").forEach(function (button) {
    button.addEventListener("click", function () {
      var message = button.closest(".message");
      if (message) {
        message.remove();
      }
    });
  });
})();
