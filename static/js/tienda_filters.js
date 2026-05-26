/**
 * @deprecated Use tienda_catalog.js — mantenido por compatibilidad con caches antiguos.
 */
(function () {
  'use strict';
  if (document.getElementById('td-catalog-root') && !window.tfTiendaLoadCatalog) {
    var s = document.createElement('script');
    s.src = '/static/js/tienda_catalog.js';
    s.async = true;
    document.body.appendChild(s);
  }
})();
