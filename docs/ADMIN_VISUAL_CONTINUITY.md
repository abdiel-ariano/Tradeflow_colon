# Continuidad visual del panel administrativo

## Objetivo

El dashboard operativo y Django Admin deben sentirse como una sola aplicación.
Cambiar entre métricas, pedidos, inventario, pagos, logística, SaaS o auditoría
no puede reemplazar el encabezado, la tipografía, el menú lateral ni el ancho
útil de la pantalla.

## Fuente única de navegación

La plantilla `templates/core/admin_rail.html` contiene el único menú lateral
administrativo. Se incluye desde:

- las vistas operativas que extienden `templates/core/base.html`;
- `templates/admin/base_site.html`, que personaliza Django Admin.

Agregar o renombrar una opción se hace una sola vez en esa plantilla. Cada
enlace debe definir `data-tf-admin-route` con el prefijo real de su ruta.
`static/js/tradeflow_admin_nav.js` utiliza ese atributo para marcar la opción
activa y abrir automáticamente su categoría.

## Contrato visual

`static/css/tradeflow_admin_continuity.css` es la última capa del sistema
administrativo y define estos invariantes:

- encabezado de 64 px, fijo en Django Admin y persistente en el dashboard;
- logotipo compacto, identidad del usuario y botón de salida equivalentes;
- menú lateral de 252 px con las mismas categorías desplegables;
- Montserrat como tipografía de interfaz, títulos, tablas y controles;
- contenido que ocupa todo el ancho restante del viewport;
- tablas sin paneles internos de desplazamiento horizontal;
- colores, bordes y espaciado alineados con TradeFlow.

La hoja debe cargarse después de los estilos heredados. En Django Admin se
carga al final de `templates/admin/base.html`; el dashboard la carga al final
de su bloque `extra_css`.

## Idioma

La experiencia administrativa usa inglés como idioma de interfaz. Las
etiquetas estáticas del índice, el encabezado y la navegación se mantienen en
inglés para evitar cambios de idioma al entrar a una vista nativa de Django.
Los valores de negocio almacenados en la base de datos no se traducen
automáticamente.

## Mantenimiento

Al agregar un módulo administrativo:

1. Registrar el modelo y confirmar el nombre de su ruta en Django Admin.
2. Añadir el enlace en `templates/core/admin_rail.html`.
3. Incluir un `data-tf-admin-route` específico; no usar rutas genéricas.
4. Mantener el texto en inglés y un icono de Material Symbols.
5. Ejecutar las pruebas de navegación, diseño y sitio administrativo.
6. Verificar dashboard, lista, formulario y vista móvil antes de desplegar.

## Pruebas de regresión

Las suites principales son:

- `core/tests/test_tradeflow_admin_navigation.py`;
- `core/tests/test_tradeflow_admin_layout.py`;
- `core/tests/test_tradeflow_admin_site.py`.

Estas pruebas comprueban la presencia del componente compartido, la carga de
la capa de continuidad, la ausencia de la tipografía serif heredada, el ancho
completo del lienzo y los accesos administrativos críticos.
