/* HotRadar 前端脚本：主题 / 菜单 / 相对时间 / 广告加载 */
(function () {
  "use strict";

  /* ---------- 主题切换 ---------- */
  var toggle = document.getElementById("theme-toggle");

  function isDark() {
    return document.documentElement.getAttribute("data-theme") === "dark" ||
      (!document.documentElement.getAttribute("data-theme") &&
        window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches);
  }

  function refreshToggleIcon() {
    if (toggle) toggle.textContent = isDark() ? "☀️" : "🌙";
  }

  if (toggle) {
    refreshToggleIcon();
    toggle.addEventListener("click", function () {
      var next = isDark() ? "light" : "dark";
      document.documentElement.setAttribute("data-theme", next);
      try { localStorage.setItem("hr-theme", next); } catch (e) { /* 隐私模式 */ }
      refreshToggleIcon();
    });
  }

  /* ---------- 移动端菜单 ---------- */
  var navToggle = document.getElementById("nav-toggle");
  var nav = document.getElementById("site-nav");
  if (navToggle && nav) {
    navToggle.addEventListener("click", function () {
      nav.classList.toggle("open");
    });
  }

  /* ---------- 回到顶部 ---------- */
  var backTop = document.getElementById("back-top");
  if (backTop) {
    window.addEventListener("scroll", function () {
      backTop.classList.toggle("show", window.scrollY > 600);
    }, { passive: true });
  }

  /* ---------- 相对时间 ---------- */
  var timeEls = document.querySelectorAll("time[data-time]");
  for (var i = 0; i < timeEls.length; i++) {
    (function (el) {
      var ts = parseInt(el.getAttribute("data-time"), 10);
      if (!ts) return;
      var diff = Date.now() / 1000 - ts;
      var txt;
      if (diff < 60) txt = "刚刚";
      else if (diff < 3600) txt = Math.floor(diff / 60) + " 分钟前";
      else if (diff < 86400) txt = Math.floor(diff / 3600) + " 小时前";
      else if (diff < 86400 * 30) txt = Math.floor(diff / 86400) + " 天前";
      else txt = new Date(ts * 1000).toLocaleDateString("zh-CN");
      el.textContent = txt;
      el.setAttribute("datetime", new Date(ts * 1000).toISOString());
    })(timeEls[i]);
  }

  /* ---------- AdSense 广告加载 ---------- */
  (function loadAds() {
    var slots = document.querySelectorAll(".ad-slot");
    if (!slots.length) return;
    if (!window.ADSENSE_CLIENT) {
      for (var i = 0; i < slots.length; i++) {
        slots[i].innerHTML =
          '<div class="ad-placeholder">广告位 · AdSense 配置后展示</div>';
      }
      return;
    }
    var s = document.createElement("script");
    s.async = true;
    s.crossOrigin = "anonymous";
    s.src = "https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=" +
      encodeURIComponent(window.ADSENSE_CLIENT);
    document.head.appendChild(s);
    for (var j = 0; j < slots.length; j++) {
      (function (slot) {
        var ins = document.createElement("ins");
        ins.className = "adsbygoogle";
        ins.style.display = "block";
        ins.setAttribute("data-ad-client", window.ADSENSE_CLIENT);
        ins.setAttribute("data-ad-slot", slot.getAttribute("data-slot") || "0");
        ins.setAttribute("data-ad-format", slot.getAttribute("data-format") || "auto");
        ins.setAttribute("data-full-width-responsive", "true");
        slot.appendChild(ins);
        try { (window.adsbygoogle = window.adsbygoogle || []).push({}); } catch (e) { /* 广告被拦截 */ }
      })(slots[j]);
    }
  })();
})();
