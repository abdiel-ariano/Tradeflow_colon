(function () {
  document.querySelectorAll('[data-cart-qty-input]').forEach(function (input) {
    var form = input.closest('form');
    if (!form) return;

    input.addEventListener('change', function () {
      var min = parseInt(input.getAttribute('min') || '1', 10);
      var max = parseInt(input.getAttribute('max') || '9999', 10);
      var value = parseInt(input.value, 10);
      if (!Number.isFinite(value)) value = min;
      value = Math.min(Math.max(value, min), max);
      input.value = String(value);
      form.submit();
    });
  });
})();
