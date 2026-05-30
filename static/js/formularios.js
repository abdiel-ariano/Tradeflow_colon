/**
 * =============================================================
 * TRADEFLOW COLÓN — static/js/formularios.js
 * =============================================================
 * Qué hace:
 *   Maneja la interactividad del wizard de Nueva Orden:
 *     - Selección de clientes existentes con previsualización
 *     - Carrito en tiempo real (Paso 2)
 *     - Validación de formularios antes de enviar
 *     - Toggle entre "cliente existente" y "cliente nuevo"
 *
 * Se carga solo en las páginas nueva_orden_paso*.html
 * =============================================================
 */

document.addEventListener('DOMContentLoaded', function () {
  initClienteSelector();
  initCarrito();
  initPaymentSelector();
  initFormValidation();
});


// ---------------------------------------------------------------
// PASO 1 — SELECTOR DE CLIENTE
// ---------------------------------------------------------------
/**
 * initClienteSelector()
 *
 * Cuando el usuario selecciona un cliente del dropdown,
 * muestra su información (nombre, email, teléfono) en una
 * tarjeta de previsualización.
 *
 * También maneja el toggle entre:
 *   - Seleccionar cliente existente
 *   - Crear nuevo cliente (muestra/oculta el formulario)
 */
function initClienteSelector() {
  const dropdown = document.getElementById('clienteDropdown');
  const preview = document.getElementById('clientePreview');
  const toggleBtn = document.getElementById('toggleNuevoCliente');
  const formNuevo = document.getElementById('formNuevoCliente');
  const seccionExistente = document.getElementById('seccionClienteExistente');

  // Previsualización al seleccionar cliente del dropdown
  if (dropdown && preview) {
    dropdown.addEventListener('change', function () {
      const option = dropdown.options[dropdown.selectedIndex];
      if (option.value) {
        const nombre = option.getAttribute('data-nombre') || option.textContent;
        const email  = option.getAttribute('data-email') || '';
        const tel    = option.getAttribute('data-tel') || '';

        preview.innerHTML =
          '<div class="cliente-preview-card">' +
          '<div class="cp-avatar">' + getInitials(nombre) + '</div>' +
          '<div>' +
          '<strong>' + escapeHtml(nombre) + '</strong>' +
          (email ? '<br><small>' + escapeHtml(email) + '</small>' : '') +
          (tel ? '<br><small>' + escapeHtml(tel) + '</small>' : '') +
          '</div></div>';
        preview.style.display = 'block';
      } else {
        preview.style.display = 'none';
      }
    });
  }

  // Toggle crear cliente nuevo
  if (toggleBtn && formNuevo && seccionExistente) {
    let modoNuevo = false;
    toggleBtn.addEventListener('click', function () {
      modoNuevo = !modoNuevo;
      formNuevo.style.display = modoNuevo ? 'block' : 'none';
      seccionExistente.style.display = modoNuevo ? 'none' : 'block';
      toggleBtn.textContent = modoNuevo
        ? '← Back to existing customers'
        : '+ Create new customer';
    });
  }
}


// ---------------------------------------------------------------
// PASO 2 — CARRITO EN TIEMPO REAL
// ---------------------------------------------------------------
/**
 * initCarrito()
 *
 * Actualiza el resumen del carrito cuando el usuario
 * cambia la cantidad en los inputs de los productos.
 * Los totales se recalculan sin necesidad de hacer submit.
 */
function initCarrito() {
  const qtyInputs = document.querySelectorAll('.qty-input');
  if (qtyInputs.length === 0) return;

  qtyInputs.forEach(function (input) {
    input.addEventListener('input', function () {
      recalcularCarrito();
    });
  });

  recalcularCarrito();
}

function recalcularCarrito() {
  const subtotalEl = document.getElementById('carritoSubtotal');
  const impuestoEl = document.getElementById('carritoImpuesto');
  const totalEl    = document.getElementById('carritoTotal');

  if (!subtotalEl) return;

  let subtotal = 0;

  // Sumar cada item del carrito visible
  document.querySelectorAll('.carrito-item').forEach(function (item) {
    const precio   = parseFloat(item.getAttribute('data-precio') || '0');
    const qtyInput = item.querySelector('.qty-input');
    const cantidad = qtyInput ? parseInt(qtyInput.value || '1') : 1;
    subtotal += precio * cantidad;
  });

  const impuesto = subtotal * 0.07;
  const total = subtotal + impuesto;

  subtotalEl.textContent = '$' + subtotal.toFixed(2);
  impuestoEl.textContent = '$' + impuesto.toFixed(2);
  totalEl.textContent    = '$' + total.toFixed(2);
}


// ---------------------------------------------------------------
// PASO 3 — SELECTOR DE MÉTODO DE PAGO
// ---------------------------------------------------------------
/**
 * initPaymentSelector()
 *
 * Resalta visualmente el método de pago seleccionado.
 */
function initPaymentSelector() {
  const options = document.querySelectorAll('.payment-option');
  options.forEach(function (option) {
    const radio = option.querySelector('input[type="radio"]');
    if (!radio) return;

    option.addEventListener('click', function () {
      // Quitar selección de todas las opciones
      options.forEach(function (o) { o.classList.remove('selected'); });
      option.classList.add('selected');
      radio.checked = true;
    });

    // Si ya está chequeado al cargar (por defecto)
    if (radio.checked) option.classList.add('selected');
  });
}


// ---------------------------------------------------------------
// VALIDACIÓN DE FORMULARIOS
// ---------------------------------------------------------------
/**
 * initFormValidation()
 *
 * Valida el formulario antes de enviarlo:
 *   - Campos requeridos no vacíos
 *   - Formato de email correcto
 *   - Muestra mensajes de error inline
 */
function initFormValidation() {
  const forms = document.querySelectorAll('form[data-validate]');
  forms.forEach(function (form) {
    form.addEventListener('submit', function (e) {
      if (!validateForm(form)) {
        e.preventDefault();
      }
    });
  });
}

function validateForm(form) {
  let valid = true;
  // Limpiar errores previos
  form.querySelectorAll('.field-error').forEach(function (el) { el.remove(); });
  form.querySelectorAll('.input-error').forEach(function (el) { el.classList.remove('input-error'); });

  form.querySelectorAll('[required]').forEach(function (input) {
    if (!input.value.trim()) {
      showFieldError(input, 'This field is required.');
      valid = false;
    } else if (input.type === 'email' && !isValidEmail(input.value)) {
      showFieldError(input, 'Enter a valid email address.');
      valid = false;
    }
  });
  return valid;
}

function showFieldError(input, message) {
  input.classList.add('input-error');
  const error = document.createElement('span');
  error.className = 'field-error';
  error.style.cssText = 'color:#e74c3c;font-size:0.75rem;margin-top:3px;display:block;';
  error.textContent = message;
  input.parentNode.appendChild(error);
}

function isValidEmail(email) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}


// ---------------------------------------------------------------
// UTILIDADES INTERNAS
// ---------------------------------------------------------------
function getInitials(name) {
  return (name || '').split(' ').map(function (w) { return w[0]; }).join('').toUpperCase().slice(0, 2);
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.appendChild(document.createTextNode(str));
  return div.innerHTML;
}
