/**
 * Shared sidebar navigation, injected into every page. Replaces the old
 * per-page top-nav links so navigation is consistent and doesn't need to be
 * hand-duplicated (and kept in sync) across 5 separate HTML files.
 *
 * Load order matters: this must load AFTER i18n.js (uses its t()/getLang()/
 * setLang()/applyTranslations() globals), and its DOMContentLoaded handler
 * intentionally builds the #lang-toggle button itself (rather than relying on
 * i18n.js's own handler to find it) since i18n.js's listener registers - and
 * therefore fires - first, before this script has injected anything into the DOM.
 */

const SIDEBAR_LINKS = [
  { href: "/", icon: "🗺️", key: "navMap" },
  { href: "/tourist-portal", icon: "🌴", key: "navPortal" },
  { href: "/rewards", icon: "🏆", key: "navRewards" },
  { href: "/hotel-portal", icon: "🏨", key: "navHotel" },
  { href: "/dashboard", icon: "🛡", key: "navDashboard" },
  { href: "/tourist", icon: "📋", key: "navTourist" },
];

function injectSidebar() {
  if (document.getElementById("app-sidebar")) return;

  const currentPath = window.location.pathname;

  const toggleBtn = document.createElement("button");
  toggleBtn.id = "sidebar-toggle";
  toggleBtn.className = "sidebar-toggle-btn";
  toggleBtn.innerHTML = "☰";
  toggleBtn.setAttribute("aria-label", "Toggle navigation");

  const sidebar = document.createElement("nav");
  sidebar.id = "app-sidebar";
  sidebar.className = "app-sidebar";
  sidebar.innerHTML = `
    <div class="sidebar-brand">
      <span class="sidebar-brand-icon">🛡</span>
      <span class="sidebar-brand-text">Tunisna</span>
    </div>
    <div class="sidebar-links">
      ${SIDEBAR_LINKS.map(
        (l) => `
        <a href="${l.href}" class="sidebar-link${currentPath === l.href ? " active" : ""}">
          <span class="sidebar-icon">${l.icon}</span>
          <span class="sidebar-label" data-i18n="${l.key}">${l.key}</span>
        </a>`
      ).join("")}
    </div>
    <div class="sidebar-footer">
      <button id="lang-toggle" class="btn-lang">EN</button>
    </div>
  `;

  const backdrop = document.createElement("div");
  backdrop.id = "sidebar-backdrop";
  backdrop.className = "sidebar-backdrop";

  document.body.prepend(backdrop);
  document.body.prepend(sidebar);
  document.body.prepend(toggleBtn);
  document.body.classList.add("has-sidebar");

  function closeSidebar() {
    sidebar.classList.remove("open");
    backdrop.classList.remove("open");
  }
  function toggleSidebarOpen() {
    sidebar.classList.toggle("open");
    backdrop.classList.toggle("open");
  }

  toggleBtn.addEventListener("click", toggleSidebarOpen);
  backdrop.addEventListener("click", closeSidebar);

  const langBtn = document.getElementById("lang-toggle");
  langBtn.addEventListener("click", cycleLang);

  applyTranslations();
}

document.addEventListener("DOMContentLoaded", injectSidebar);
