// FieldOps Nexus UI behaviour. Business rules live on the server; this file only enhances.
(function () {
  // Confirmation dialogs: <button data-confirm="Message" data-confirm-title="Title">
  document.addEventListener("click", function (ev) {
    var btn = ev.target.closest("[data-confirm]");
    if (!btn || btn.dataset.confirmed === "1") return;
    ev.preventDefault();
    var dlg = document.getElementById("fx-confirm");
    document.getElementById("fx-confirm-title").textContent = btn.dataset.confirmTitle || "Please confirm";
    document.getElementById("fx-confirm-text").textContent = btn.dataset.confirm;
    dlg.returnValue = "";
    dlg.addEventListener("close", function onClose() {
      dlg.removeEventListener("close", onClose);
      if (dlg.returnValue === "ok") {
        btn.dataset.confirmed = "1";
        if (btn.form && btn.form.requestSubmit) { btn.form.requestSubmit(btn); } else { btn.click(); }
      }
    });
    dlg.showModal();
  });

  // Drawer: <button data-drawer-open="id"> / <button data-drawer-close>
  document.addEventListener("click", function (ev) {
    var open = ev.target.closest("[data-drawer-open]");
    if (open) { var d = document.getElementById(open.dataset.drawerOpen); if (d) d.hidden = false; }
    if (ev.target.closest("[data-drawer-close]")) {
      var host = ev.target.closest(".fx-drawer"); if (host) host.hidden = true;
    }
  });

  // Close search results when clicking elsewhere
  document.addEventListener("click", function (ev) {
    if (!ev.target.closest(".fx-search")) {
      var r = document.getElementById("fx-search-results"); if (r) r.innerHTML = "";
    }
  });
})();

/* Delegated handlers (replace inline onclick attributes so the Content-Security-Policy can forbid them). */
document.addEventListener("click", function (e) {
  var nav = e.target.closest("[data-fx-toggle-nav]");
  if (nav) { var l = document.getElementById("fx-layout"); if (l) l.classList.toggle("fx-nav-open"); return; }
  if (e.target.closest("[data-fx-print]")) window.print();
});

/* Asset form: choosing another category reloads the page with the typed values so the category's custom attributes
   appear (the server builds and validates those fields). */
document.addEventListener("change", function (e) {
  var sel = e.target.closest("select[data-category-reload]");
  if (!sel || !sel.form) return;
  var params = new URLSearchParams();
  new FormData(sel.form).forEach(function (value, key) {
    if (typeof value === "string" && key !== "csrfmiddlewaretoken" && key.indexOf("attr_") !== 0 && value !== "") {
      params.set(key, value);
    }
  });
  window.location.search = params.toString();
});

/* Shell behaviour (reference Sidebar.tsx / Header.tsx): collapsible nav groups, collapsed sidebar, initials, breadcrumb relocation.
   Navigation content and permissions are rendered by the server; this only toggles presentation and remembers it in localStorage. */
(function () {
  var store = {
    get: function (k) { try { return window.localStorage.getItem(k); } catch (e) { return null; } },
    set: function (k, v) { try { window.localStorage.setItem(k, v); } catch (e) { /* storage unavailable */ } }
  };
  var layout = document.getElementById("fx-layout");
  if (!layout) return;
  var toggle = layout.querySelector("[data-fx-collapse]");
  function setCollapsed(on) {
    layout.classList.toggle("fx-collapsed", on);
    if (toggle) toggle.setAttribute("aria-pressed", on ? "true" : "false");
  }
  setCollapsed(store.get("fx.sidebar") === "collapsed");
  if (toggle) toggle.addEventListener("click", function () {
    var on = !layout.classList.contains("fx-collapsed");
    setCollapsed(on); store.set("fx.sidebar", on ? "collapsed" : "open");
  });

  var saved = {};
  try { saved = JSON.parse(store.get("fx.groups") || "{}"); } catch (e) { saved = {}; }
  var groups = layout.querySelectorAll(".fx-group");
  groups.forEach(function (g, i) {
    var name = g.getAttribute("data-fx-group");
    var active = g.hasAttribute("data-fx-active");
    if (active) g.classList.add("has-active");
    var open = active || (name in saved ? saved[name] : i === 0);
    g.classList.toggle("is-open", open);
    g.querySelector(".fx-group-toggle").setAttribute("aria-expanded", open ? "true" : "false");
  });
  layout.addEventListener("click", function (e) {
    var btn = e.target.closest(".fx-group-toggle");
    if (!btn || layout.classList.contains("fx-collapsed") && window.innerWidth >= 992) return;
    var g = btn.parentElement, open = !g.classList.contains("is-open");
    g.classList.toggle("is-open", open);
    btn.setAttribute("aria-expanded", open ? "true" : "false");
    saved[g.getAttribute("data-fx-group")] = open; store.set("fx.groups", JSON.stringify(saved));
  });

  document.querySelectorAll("[data-fx-initials]").forEach(function (el) {
    var parts = (el.getAttribute("data-fx-initials") || "").trim().split(/\s+/).filter(Boolean);
    if (parts.length) el.textContent = ((parts[0][0] || "") + (parts.length > 1 ? parts[parts.length - 1][0] : "")).toUpperCase();
  });

  var crumbs = document.querySelector("main [data-fx-crumbs]");
  var slot = document.getElementById("fx-crumbs");
  if (crumbs && slot) {
    while (slot.firstChild) slot.removeChild(slot.firstChild);
    slot.appendChild(crumbs);
  }
})();

/* Sidebar: when several entries match the current URL prefix, highlight only the most specific one. */
(function () {
  var active = [].slice.call(document.querySelectorAll(".fx-nav-link.active[href], .fx-nav-child.active[href]"));
  if (active.length < 2) return;
  var best = active.reduce(function (a, b) { return (b.getAttribute("href").length > a.getAttribute("href").length) ? b : a; });
  active.forEach(function (el) { if (el !== best) el.classList.remove("active"); });
})();
