/**
 * =============================================================
 * TRADEFLOW COLÓN — static/js/main.js
 * =============================================================
 * Qué hace:
 *   Funciones JavaScript globales cargadas en base.html.
 *   No depende de ningún framework externo (Vanilla JS puro).
 *
 * Funciones incluidas:
 *   - initMessages()      → Auto-cierra las alertas de Django
 *   - initSidebar()       → Toggle del sidebar en móvil
 *   - initSearchBar()     → Foco en la barra de búsqueda
 *   - initDropdowns()     → Menús desplegables del topbar
 *   - initDatePills()     → Botones de período en el dashboard
 *   - initTableCheckboxes() → Seleccionar filas en tablas
 *
 * Cómo funciona:
 *   Se llama document.addEventListener('DOMContentLoaded', ...)
 *   para ejecutar todo después de que el HTML esté listo.
 * =============================================================
 */

document.addEventListener('DOMContentLoaded', function () {
  initMessages();
  initSidebar();
  initDropdowns();
  initTableCheckboxes();
});


// ---------------------------------------------------------------
// ALERTAS / MENSAJES DE DJANGO
// ---------------------------------------------------------------
/**
 * initMessages()
 *
 * Agrega botón de cierre a cada alerta y las oculta
 * automáticamente después de 5 segundos.
 */
function initMessages() {
  const alerts = document.querySelectorAll('.alert');

  alerts.forEach(function (alert) {
    // Auto-cierre a los 5 segundos
    const timer = setTimeout(function () {
      fadeOut(alert);
    }, 5000);

    // Botón de cierre manual
    const closeBtn = alert.querySelector('.alert-close');
    if (closeBtn) {
      closeBtn.addEventListener('click', function () {
        clearTimeout(timer);
        fadeOut(alert);
      });
    }
  });
}

/**
 * fadeOut(element)
 * Anima la desaparición y luego elimina el elemento del DOM.
 */
function fadeOut(element) {
  element.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
  element.style.opacity = '0';
  element.style.transform = 'translateX(10px)';
  setTimeout(function () {
    if (element.parentNode) {
      element.parentNode.removeChild(element);
    }
  }, 300);
}


// ---------------------------------------------------------------
// SIDEBAR MÓVIL
// ---------------------------------------------------------------
/**
 * initSidebar()
 *
 * En pantallas pequeñas (< 1024px), el sidebar está oculto.
 * El botón de hamburguesa con id="sidebarToggle" lo abre/cierra.
 * También cierra el sidebar al hacer clic fuera de él.
 */
function initSidebar() {
  const toggleBtn = document.getElementById('sidebarToggle');
  const sidebar = document.querySelector('.sidebar');
  const overlay = document.getElementById('sidebarOverlay');

  if (!toggleBtn || !sidebar) return;

  toggleBtn.addEventListener('click', function () {
    sidebar.classList.toggle('open');
    if (overlay) overlay.classList.toggle('active');
  });

  // Cerrar al hacer clic en el overlay
  if (overlay) {
    overlay.addEventListener('click', function () {
      sidebar.classList.remove('open');
      overlay.classList.remove('active');
    });
  }
}


// ---------------------------------------------------------------
// DROPDOWNS GENÉRICOS
// ---------------------------------------------------------------
/**
 * initDropdowns()
 *
 * Controla la apertura/cierre de cualquier menú desplegable.
 * Uso en HTML:
 *   <div class="dropdown">
 *     <button class="dropdown-trigger">Abrir</button>
 *     <div class="dropdown-menu">...</div>
 *   </div>
 */
function initDropdowns() {
  const dropdowns = document.querySelectorAll('.dropdown');

  dropdowns.forEach(function (dropdown) {
    const trigger = dropdown.querySelector('.dropdown-trigger');
    const menu = dropdown.querySelector('.dropdown-menu');

    if (!trigger || !menu) return;

    trigger.addEventListener('click', function (e) {
      e.stopPropagation();
      // Cerrar otros dropdowns abiertos
      document.querySelectorAll('.dropdown-menu.open').forEach(function (m) {
        if (m !== menu) m.classList.remove('open');
      });
      menu.classList.toggle('open');
    });
  });

  // Cerrar todos al hacer clic fuera
  document.addEventListener('click', function () {
    document.querySelectorAll('.dropdown-menu.open').forEach(function (m) {
      m.classList.remove('open');
    });
  });
}


// ---------------------------------------------------------------
// CHECKBOXES DE TABLA (seleccionar todos)
// ---------------------------------------------------------------
/**
 * initTableCheckboxes()
 *
 * El checkbox en el <thead> con id="selectAll" selecciona o
 * deselecciona todos los checkboxes de las filas del tbody.
 */
function initTableCheckboxes() {
  const selectAll = document.getElementById('selectAll');
  if (!selectAll) return;

  selectAll.addEventListener('change', function () {
    const rowCheckboxes = document.querySelectorAll('.row-checkbox');
    rowCheckboxes.forEach(function (cb) {
      cb.checked = selectAll.checked;
    });
    updateBulkActions();
  });

  // Actualizar el "seleccionar todos" si se cambia individualmente
  document.querySelectorAll('.row-checkbox').forEach(function (cb) {
    cb.addEventListener('change', function () {
      updateBulkActions();
      const total = document.querySelectorAll('.row-checkbox').length;
      const checked = document.querySelectorAll('.row-checkbox:checked').length;
      if (selectAll) selectAll.indeterminate = checked > 0 && checked < total;
    });
  });
}

/**
 * updateBulkActions()
 * Muestra u oculta la barra de acciones masivas según selección.
 */
function updateBulkActions() {
  const checked = document.querySelectorAll('.row-checkbox:checked').length;
  const bulkBar = document.getElementById('bulkActions');
  if (bulkBar) {
    bulkBar.style.display = checked > 0 ? 'flex' : 'none';
    const countEl = bulkBar.querySelector('.bulk-count');
    if (countEl) countEl.textContent = checked + ' seleccionado' + (checked > 1 ? 's' : '');
  }
}


// ---------------------------------------------------------------
// UTILIDADES EXPORTADAS
// ---------------------------------------------------------------

/**
 * formatCurrency(amount)
 * Formatea un número como moneda USD.
 * Ejemplo: formatCurrency(1234.5) → "$1,234.50"
 */
function formatCurrency(amount) {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
  }).format(amount);
}

/**
 * formatDate(dateStr)
 * Convierte una fecha ISO a formato DD/MM/YYYY.
 * Ejemplo: formatDate('2026-03-14') → "14/03/2026"
 */
function formatDate(dateStr) {
  const d = new Date(dateStr);
  return d.toLocaleDateString('es-PA');
}

/**
 * showToast(message, type)
 * Muestra un mensaje temporal en la esquina superior derecha.
 * type: 'success' | 'error' | 'warning' | 'info'
 */
function showToast(message, type) {
  type = type || 'info';
  const container = document.querySelector('.messages-container') || createMessagesContainer();
  const toast = document.createElement('div');
  toast.className = 'alert alert-' + type;
  toast.innerHTML = message + '<button class="alert-close" onclick="this.parentElement.remove()">✕</button>';
  container.appendChild(toast);
  setTimeout(function () { fadeOut(toast); }, 4000);
}

function createMessagesContainer() {
  const div = document.createElement('div');
  div.className = 'messages-container';
  document.body.appendChild(div);
  return div;
}
