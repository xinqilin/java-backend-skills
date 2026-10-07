// Picks the page language before first paint, and wires the toggle button.
// Preference order: saved choice, then the browser language, then English.
(function () {
  var KEY = "java-backend-docs-lang";
  var root = document.documentElement;

  function saved() {
    try { return window.localStorage.getItem(KEY); } catch (e) { return null; }
  }

  function save(lang) {
    try { window.localStorage.setItem(KEY, lang); } catch (e) { /* storage unavailable: keep the in-page choice only */ }
  }

  function browserPrefersChinese() {
    var langs = navigator.languages || [navigator.language || ""];
    for (var i = 0; i < langs.length; i++) {
      if (/^zh/i.test(langs[i])) return true;
    }
    return false;
  }

  function apply(lang) {
    root.setAttribute("data-lang", lang);
    root.setAttribute("lang", lang === "zh" ? "zh-Hant-TW" : "en");
    var buttons = document.querySelectorAll(".lang-toggle");
    for (var i = 0; i < buttons.length; i++) {
      buttons[i].textContent = lang === "zh" ? "English" : "中文";
      buttons[i].setAttribute("aria-label", lang === "zh" ? "Switch to English" : "切換成中文");
    }
  }

  var initial = saved();
  if (initial !== "en" && initial !== "zh") initial = browserPrefersChinese() ? "zh" : "en";
  apply(initial);

  document.addEventListener("DOMContentLoaded", function () {
    apply(root.getAttribute("data-lang") || "en");
    var buttons = document.querySelectorAll(".lang-toggle");
    for (var i = 0; i < buttons.length; i++) {
      buttons[i].addEventListener("click", function () {
        var next = root.getAttribute("data-lang") === "zh" ? "en" : "zh";
        apply(next);
        save(next);
      });
    }
  });
})();
