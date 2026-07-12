/**
 * TradeFlow Colón — CFZ company map (Leaflet + OpenStreetMap, no API key).
 * Reads marker payload from #tf-cfz-map-data (json_script from Django).
 */
(function () {
  'use strict';

  var dataEl = document.getElementById('tf-cfz-map-data');
  var mapEl = document.getElementById('tf-cfz-map');
  if (!dataEl || !mapEl || typeof L === 'undefined') {
    return;
  }

  var payload;
  try {
    payload = JSON.parse(dataEl.textContent);
  } catch (e) {
    return;
  }

  var markers = payload.markers || [];
  var center = payload.center || { lat: 9.3667, lng: -79.9, zoom: 13 };
  var labels = payload.labels || {};
  var verifiedLabel = labels.verified || 'Verified seller';
  var pendingLabel = labels.pending || 'Pending verification';
  var productsLabel = labels.products || 'products';
  var viewCatalogLabel = labels.view_catalog || 'View catalog';

  var map = L.map(mapEl, { scrollWheelZoom: true }).setView(
    [center.lat, center.lng],
    center.zoom || 13
  );

  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution:
      '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a>',
  }).addTo(map);

  var cluster = typeof L.markerClusterGroup === 'function'
    ? L.markerClusterGroup({
        maxClusterRadius: 48,
        spiderfyOnMaxZoom: true,
        showCoverageOnHover: false,
      })
    : null;

  var bounds = [];

  markers.forEach(function (item) {
    var lat = item.lat;
    var lng = item.lng;
    if (lat == null || lng == null) {
      return;
    }
    bounds.push([lat, lng]);

    var icon = L.divIcon({
      className: 'tf-cfz-marker-wrap',
      html:
        '<span class="tf-cfz-marker tf-cfz-marker--' +
        (item.verified ? 'verified' : 'pending') +
        '" aria-hidden="true"></span>',
      iconSize: [28, 28],
      iconAnchor: [14, 28],
      popupAnchor: [0, -26],
    });

    var popupHtml =
      '<div class="tf-cfz-popup">' +
      '<strong>' +
      escapeHtml(item.name) +
      '</strong>' +
      '<p class="tf-cfz-popup__meta">' +
      (item.verified ? verifiedLabel : pendingLabel) +
      ' · ' +
      item.products +
      ' ' +
      productsLabel +
      '</p>' +
      (item.categories
        ? '<p class="tf-cfz-popup__cats">' + escapeHtml(item.categories) + '</p>'
        : '') +
      '<a class="tf-cfz-popup__btn" href="' +
      escapeHtml(item.catalog_url) +
      '">' +
      escapeHtml(viewCatalogLabel) +
      '</a>' +
      '</div>';

    var marker = L.marker([lat, lng], { icon: icon }).bindPopup(popupHtml, {
      maxWidth: 300,
      className: 'tf-cfz-popup-shell',
    });

    if (cluster) {
      cluster.addLayer(marker);
    } else {
      marker.addTo(map);
    }
  });

  if (cluster) {
    map.addLayer(cluster);
  }

  if (bounds.length > 1) {
    map.fitBounds(bounds, { padding: [40, 40], maxZoom: 14 });
  } else if (bounds.length === 1) {
    map.setView(bounds[0], 15);
  }

  function escapeHtml(str) {
    return String(str || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }
})();
