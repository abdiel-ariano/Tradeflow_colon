/**
 * TradeFlow Colón — CFZ company map (Leaflet + OpenStreetMap, no API key).
 * Sidebar list syncs with map markers; filter by name and verified status.
 */
(function () {
  'use strict';

  var dataEl = document.getElementById('tf-cfz-map-data');
  var mapEl = document.getElementById('tf-cfz-map');
  var listEl = document.getElementById('tf-cfz-map-list');
  var statsEl = document.getElementById('tf-cfz-map-stats');
  var filterEl = document.getElementById('tf-cfz-map-filter');
  var verifiedOnlyEl = document.getElementById('tf-cfz-verified-only');

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
  var filterPlaceholder = labels.filter_placeholder || 'Filter companies…';
  var verifiedOnlyLabel = labels.verified_only || 'Verified only';
  var noResultsLabel = labels.no_results || 'No companies match your filter';

  if (filterEl && !filterEl.getAttribute('placeholder')) {
    filterEl.setAttribute('placeholder', filterPlaceholder);
  }

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

  var markerById = {};
  var listItemById = {};
  var bounds = [];
  var activeId = null;

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

    marker.on('click', function () {
      setActiveItem(item.id);
    });

    markerById[item.id] = marker;

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

  function updateStats(visibleCount) {
    if (!statsEl) {
      return;
    }
    var total = markers.length;
    var verified = markers.filter(function (m) { return m.verified; }).length;
    if (visibleCount != null && visibleCount !== total) {
      statsEl.textContent = visibleCount + ' / ' + total + ' · ' + verified + ' ' + verifiedLabel.toLowerCase();
    } else {
      statsEl.textContent = total + ' companies · ' + verified + ' ' + verifiedLabel.toLowerCase();
    }
  }

  function setActiveItem(id) {
    activeId = id;
    Object.keys(listItemById).forEach(function (key) {
      var li = listItemById[key];
      if (li) {
        li.classList.toggle('is-active', String(key) === String(id));
      }
    });
    var activeLi = listItemById[id];
    if (activeLi && typeof activeLi.scrollIntoView === 'function') {
      activeLi.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }
  }

  function focusMarker(item) {
    var marker = markerById[item.id];
    if (!marker) {
      return;
    }
    setActiveItem(item.id);

    function openPopup() {
      map.setView([item.lat, item.lng], Math.max(map.getZoom(), 15), { animate: true });
      marker.openPopup();
    }

    if (cluster && typeof cluster.zoomToShowLayer === 'function') {
      cluster.zoomToShowLayer(marker, openPopup);
    } else {
      openPopup();
    }
  }

  function renderList(filtered) {
    if (!listEl) {
      return;
    }

    listEl.innerHTML = '';
    listItemById = {};

    if (!filtered.length) {
      var empty = document.createElement('li');
      empty.className = 'map-zlc-list__empty';
      empty.textContent = noResultsLabel;
      listEl.appendChild(empty);
      updateStats(0);
      return;
    }

    filtered.forEach(function (item) {
      var li = document.createElement('li');
      li.className = 'map-zlc-list__item';
      li.setAttribute('role', 'listitem');

      var btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'map-zlc-list__btn';
      btn.innerHTML =
        '<span class="map-zlc-list__name">' +
        escapeHtml(item.name) +
        '</span>' +
        '<span class="map-zlc-list__meta">' +
        item.products +
        ' ' +
        escapeHtml(productsLabel) +
        (item.categories ? ' · ' + escapeHtml(item.categories) : '') +
        '</span>' +
        '<span class="map-zlc-list__badge map-zlc-list__badge--' +
        (item.verified ? 'verified' : 'pending') +
        '">' +
        escapeHtml(item.verified ? verifiedLabel : pendingLabel) +
        '</span>';

      btn.addEventListener('click', function () {
        focusMarker(item);
      });

      li.appendChild(btn);
      listEl.appendChild(li);
      listItemById[item.id] = li;

      if (String(activeId) === String(item.id)) {
        li.classList.add('is-active');
      }
    });

    updateStats(filtered.length);
  }

  function applyFilters() {
    var query = (filterEl && filterEl.value ? filterEl.value : '').trim().toLowerCase();
    var verifiedOnly = verifiedOnlyEl && verifiedOnlyEl.checked;

    var filtered = markers.filter(function (item) {
      if (verifiedOnly && !item.verified) {
        return false;
      }
      if (!query) {
        return true;
      }
      var haystack = (item.name + ' ' + (item.categories || '')).toLowerCase();
      return haystack.indexOf(query) !== -1;
    });

    renderList(filtered);
  }

  if (filterEl) {
    filterEl.addEventListener('input', applyFilters);
  }
  if (verifiedOnlyEl) {
    verifiedOnlyEl.addEventListener('change', applyFilters);
  }

  applyFilters();

  /* Reflow map after split layout paints */
  setTimeout(function () {
    map.invalidateSize();
  }, 120);

  window.addEventListener('resize', function () {
    map.invalidateSize();
  });

  function escapeHtml(str) {
    return String(str || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }
})();
