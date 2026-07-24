/**
 * Highlights the most specific TradeFlow admin route in the persistent rail.
 */
(function () {
  "use strict";

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
})();
