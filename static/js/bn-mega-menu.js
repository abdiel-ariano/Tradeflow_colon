/**
 * TradeFlow Colón — bn-mega-menu.js
 *
 * Mega menú «Todas las categorías» del navbar comprador.
 * Al pasar el mouse sobre una categoría (columna izquierda), activa
 * el panel de productos correspondiente en la columna derecha.
 */
(function () {
  'use strict';

  var left = document.getElementById('bn-mega-left');
  var right = document.getElementById('bn-mega-right');
  if (!left || !right) return;

  var cats = left.querySelectorAll('.bn-mega-cat[data-mega-panel]');
  var panels = right.querySelectorAll('.bn-mega-panel[data-mega-panel]');

  function activate(panelId) {
    cats.forEach(function (cat) {
      var active = cat.getAttribute('data-mega-panel') === panelId;
      cat.classList.toggle('is-active', active);
    });
    panels.forEach(function (panel) {
      var active = panel.getAttribute('data-mega-panel') === panelId;
      panel.classList.toggle('is-active', active);
      if (active) {
        panel.removeAttribute('hidden');
      } else {
        panel.setAttribute('hidden', '');
      }
    });
  }

  left.addEventListener('mouseover', function (e) {
    var cat = e.target.closest('.bn-mega-cat[data-mega-panel]');
    if (!cat) return;
    activate(cat.getAttribute('data-mega-panel'));
  });
})();
