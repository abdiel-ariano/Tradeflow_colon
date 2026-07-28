/**
 * Keeps the shared TradeFlow administration rail route-aware.
 *
 * The dashboard and Django Admin render the same navigation partial. The
 * current destination opens automatically, while opening another category
 * closes its siblings. The selected category is preserved for the session.
 */
(function () {
  "use strict";

  /**
   * Return whether a route prefix matches the current browser path.
   *
   * @param {string} currentPath Current URL path.
   * @param {string} route Configured navigation route.
   * @returns {boolean} True when the route represents the current page.
   */
  function routeMatches(currentPath, route) {
    if (!route) return false;
    if (route === "/admin/") return currentPath === route;
    return currentPath.indexOf(route) === 0;
  }

  /** Mark the most specific shared-rail destination as active. */
  function highlightSharedRail() {
    var rail = document.getElementById("admRail");
    if (!rail) return;

    var activeKey = rail.getAttribute("data-nav-active") || "";
    var currentPath = window.location.pathname;
    var links = Array.prototype.slice.call(
      rail.querySelectorAll("a.adm-rail-link")
    );
    var bestMatch = null;

    links.forEach(function (link) {
      var key = link.getAttribute("data-adm-nav") || "";
      var route = link.getAttribute("data-tf-admin-route") || "";
      var keyMatches = Boolean(activeKey && key === activeKey);
      var pathMatches = routeMatches(currentPath, route);
      var matchWeight = keyMatches ? 10000 : route.length;

      if (
        (keyMatches || pathMatches) &&
        (!bestMatch || matchWeight > bestMatch.weight)
      ) {
        bestMatch = { link: link, weight: matchWeight };
      }
    });

    if (bestMatch) {
      bestMatch.link.classList.add("is-active");
      bestMatch.link.setAttribute("aria-current", "page");
    }
  }

  /**
   * Convert section labels and links into accessible accordion groups.
   *
   * @param {HTMLElement|null} nav Navigation container.
   * @param {string} labelSelector Selector for category labels.
   * @param {string} storageKey Session storage key.
   */
  function buildAccordion(nav, labelSelector, storageKey) {
    if (!nav || nav.getAttribute("data-accordion-ready") === "true") {
      return;
    }

    var children = Array.prototype.slice.call(nav.children);
    var groups = [];
    var currentBody = null;

    nav.textContent = "";

    children.forEach(function (node) {
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
    highlightSharedRail();
    buildAccordion(
      document.querySelector(".adm-rail-nav"),
      ".adm-rail-section-label",
      "tradeflow-admin-group"
    );
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initializeNavigation);
  } else {
    initializeNavigation();
  }
})();
