/**
 * =============================================================
 * TRADEFLOW COLÓN — static/js/filtros.js
 * =============================================================
 * Qué hace:
 *   Maneja la interactividad de la página de Órdenes:
 *     - Búsqueda en tiempo real (con debounce para no saturar)
 *     - Envío automático del formulario al cambiar selectores
 *     - Botón de limpiar filtros
 *     - Exportación a CSV básica
 *
 * Cómo funciona:
 *   Este archivo se carga SOLO en ordenes.html con:
 *   <script src="{% static 'js/filtros.js' %}"></script>
 * =============================================================
 */

document.addEventListener('DOMContentLoaded', function () {
  initFiltros();
  initExportCSV();
});


// ---------------------------------------------------------------
// FORMULARIO DE FILTROS
// ---------------------------------------------------------------
function initFiltros() {
  const form = document.getElementById('filtrosForm');
  if (!form) return;

  // Auto-submit al cambiar dropdowns (estado, método de pago)
  const selects = form.querySelectorAll('select');
  selects.forEach(function (select) {
    select.addEventListener('change', function () {
      form.submit();
    });
  });

  // Auto-submit al cambiar fechas
  const dateInputs = form.querySelectorAll('input[type="date"]');
  dateInputs.forEach(function (input) {
    input.addEventListener('change', function () {
      // Pequeño delay para permitir que el usuario elija ambas fechas
      setTimeout(function () { form.submit(); }, 300);
    });
  });

  // Búsqueda con debounce (espera 500ms después de escribir)
  const searchInput = form.querySelector('input[name="busqueda"]');
  if (searchInput) {
    let debounceTimer;
    searchInput.addEventListener('input', function () {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(function () {
        form.submit();
      }, 500);
    });
  }

  // Botón limpiar: resetea todos los campos y envía
  const btnLimpiar = document.getElementById('btnLimpiar');
  if (btnLimpiar) {
    btnLimpiar.addEventListener('click', function () {
      form.reset();
      // Remover todos los parámetros GET y recargar limpio
      window.location.href = window.location.pathname;
    });
  }
}


// ---------------------------------------------------------------
// EXPORTAR A CSV
// ---------------------------------------------------------------
/**
 * initExportCSV()
 *
 * Lee las filas visibles de la tabla y genera un archivo CSV
 * para descarga directa. No requiere backend.
 *
 * Nota: Solo exporta lo visible en pantalla (la página actual).
 * Para exportar todo, implementar en views.py con StreamingHttpResponse.
 */
function initExportCSV() {
  const btnCSV = document.getElementById('btnExportCSV');
  if (!btnCSV) return;

  btnCSV.addEventListener('click', function () {
    const table = document.querySelector('.data-table');
    if (!table) return;

    const rows = [];

    // Encabezados
    const headers = [];
    table.querySelectorAll('thead th').forEach(function (th) {
      // Saltar columna de checkbox y acciones
      const text = th.textContent.trim();
      if (text && text !== '✓' && text !== 'Acc.') {
        headers.push('"' + text + '"');
      }
    });
    rows.push(headers.join(','));

    // Filas de datos
    table.querySelectorAll('tbody tr').forEach(function (tr) {
      const cells = [];
      tr.querySelectorAll('td').forEach(function (td, index) {
        // Saltar primera (checkbox) y última (acciones)
        const totalCols = tr.querySelectorAll('td').length;
        if (index === 0 || index === totalCols - 1) return;
        const text = td.textContent.trim().replace(/"/g, '""');
        cells.push('"' + text + '"');
      });
      if (cells.length > 0) rows.push(cells.join(','));
    });

    // Crear y descargar el archivo
    const csvContent = '\uFEFF' + rows.join('\n'); // BOM para Excel en español
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'ordenes_tradeflow_' + new Date().toISOString().slice(0, 10) + '.csv';
    link.click();
    URL.revokeObjectURL(url);

    showToast('Archivo CSV descargado correctamente.', 'success');
  });
}
