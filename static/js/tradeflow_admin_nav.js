/**
 * Keeps TradeFlow admin navigation active, compact, and route-aware.
 *
 * Both Django Admin and the custom operations dashboard use the same
 * accordion behavior. The group containing the current page opens
 * automatically, while opening another group closes its siblings.
 */
(function () {
  "use strict";

  /** Mark the most specific Django Admin route as active. */
  function highlightSystemRail() {
    var rail = document.getElementById("tfSystemRail");
    if (!rail) return;

    var currentPath = window.location.pathname;
    var links = Array.prototype.slice.call(
      rail.querySelectorAll("a[data-tf-admin-route]")
    );
    var bestMatch = null;

    links.forEach(function (link) {
      var route = link.getAttribute("data-tf-admin-route") || "";
      var matches = route === "/admin/"
        ? currentPath === route
        : currentPath.indexOf(route) === 0;

      if (matches && (!bestMatch || route.length > bestMatch.route.length)) {
        bestMatch = { link: link, route: route };
      }
    });

    if (bestMatch) {
      bestMatch.link.classList.add("is-active");
      bestMatch.link.setAttribute("aria-current", "page");
    }
  }

  /** Mark the current custom dashboard destination as active. */
  function highlightDashboardRail() {
    var rail = document.getElementById("admRail");
    if (!rail) return;

    var activeKey = rail.getAttribute("data-nav-active") || "";
    var currentPath = window.location.pathname;
    var links = Array.prototype.slice.call(
      rail.querySelectorAll("a.adm-rail-link")
    );
    var activeLink = null;

    links.forEach(function (link) {
      var key = link.getAttribute("data-adm-nav") || "";
      var routeMatches = link.pathname === currentPath;
      var keyMatches = activeKey && key === activeKey;

      if (!activeLink && (keyMatches || routeMatches)) {
        activeLink = link;
      }
    });

    if (activeLink) {
      activeLink.classList.add("is-active");
      activeLink.setAttribute("aria-current", "page");
    }
  }

  /** Convert section labels and links into accessible accordion groups. */
  function buildAccordion(nav, labelSelector, storageKey) {
    if (!nav || nav.getAttribute("data-accordion-ready") === "true") {
      return;
    }

    var children = Array.prototype.slice.call(nav.children);
    var groups = [];
    var currentBody = null;

    nav.textContent = "";

    children.forEach(function (node, index) {
      if (node.matches(labelSelector)) {
        var details = document.createElement("details");
        var summary = document.createElement("summary");
        var label = document.createElement("span");
        var icon = document.createElement("span");
        var body = document.createElement("div");

        details.className = "tf-rail-group";
        details.setAttribute("data-rail-group", String(groups.length));
        summary.className = "tf-rail-group__summary";
        body.className = "tf-rail-group__body";
        label.textContent = node.textContent.trim();
        icon.className = "material-symbols-rounded tf-rail-group__icon";
        icon.setAttribute("aria-hidden", "true");
        icon.textContent = "expand_more";

        summary.appendChild(label);
        summary.appendChild(icon);
        details.appendChild(summary);
        details.appendChild(body);
        nav.appendChild(details);
        groups.push(details);
        currentBody = body;
        return;
      }

      if (currentBody) {
        currentBody.appendChild(node);
      } else {
        nav.appendChild(node);
      }
    });

    if (!groups.length) return;

    var activeGroup = groups.find(function (group) {
      return Boolean(group.querySelector(".is-active, [aria-current='page']"));
    });
    var savedIndex = window.sessionStorage.getItem(storageKey);
    var savedGroup = groups.find(function (group) {
      return group.getAttribute("data-rail-group") === savedIndex;
    });
    var initialGroup = activeGroup || savedGroup || groups[0];

    initialGroup.open = true;

    groups.forEach(function (group) {
      group.addEventListener("toggle", function () {
        if (!group.open) return;

        groups.forEach(function (sibling) {
          if (sibling !== group) sibling.open = false;
        });
        window.sessionStorage.setItem(
          storageKey,
          group.getAttribute("data-rail-group") || "0"
        );
      });
    });

    nav.setAttribute("data-accordion-ready", "true");
  }

  function initializeNavigation() {
    highlightSystemRail();
    highlightDashboardRail();
    buildAccordion(
      document.querySelector(".tf-system-rail__nav"),
      ".tf-system-rail__section",
      "tradeflow-admin-group"
    );
    buildAccordion(
      document.querySelector(".adm-rail-nav"),
      ".adm-rail-section-label",
      "tradeflow-dashboard-group"
    );
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initializeNavigation);
  } else {
    initializeNavigation();
  }
})();
