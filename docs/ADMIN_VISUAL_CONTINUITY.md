# Sistema visual administrativo de TradeFlow

## Objetivo

Todas las rutas de supervisión deben sentirse como una sola aplicación. El
administrador nativo, el dashboard de ventas y el panel SaaS comparten la
misma navegación, tipografía, paleta, ancho útil y comportamiento responsive.

## Propietario del shell

`django-unfold` es el único propietario de la estructura administrativa:

- navegación lateral y estado activo;
- encabezado, cuenta y cierre de sesión;
- formularios, filtros, tablas y acciones;
- adaptación para tablet y móvil;
- modo visual claro y estable.

TradeFlow no reemplaza `admin/base.html`. Esto permite que las mejoras y
correcciones de Unfold lleguen a todas las pantallas sin mantener una copia
completa del HTML interno de Django Admin.

## Configuración

`tradeflow_colon/settings.py` contiene el diccionario `UNFOLD`. Allí se
mantienen:

- logotipo e icono oficiales;
- grupos y destinos del menú lateral;
- paleta base y color de acción;
- comportamiento de historial, regreso y vista pública;
- tema claro forzado para evitar cambios inesperados entre pantallas.

La navegación se agrupa en Summary, Commerce, Companies and users, Logistics,
SaaS and platform y Audit. Sus enlaces abren vistas reales protegidas por los
permisos de Django.

## Identidad visual

`static/css/tradeflow_unfold.css` es la única capa de personalización global.
Define:

- Montserrat como tipografía administrativa;
- azul marino para navegación y estructura;
- azul para información y enlaces;
- naranja para acciones, foco y estados activos;
- blanco y grises claros para superficies y separación;
- lienzo sin un ancho máximo artificial;
- componentes de la portada administrativa.

La hoja se carga al final desde `templates/admin/base_site.html`, después de
los estilos de Unfold. Esa plantilla también expone bloques de compatibilidad
para los scripts y estilos específicos de los dashboards.

## Dashboard de ventas y panel SaaS

`templates/core/dashboard.html` y
`templates/core/admin_saas_dashboard.html` extienden
`templates/admin/base_site.html`. No incluyen otra cabecera ni otro menú.

El módulo React de SaaS se monta como contenido de página. No crea un segundo
shell, no fija un encabezado propio y no limita el lienzo a 1400 px. Su fuente
y tokens se alinean con TradeFlow desde:

- `frontend/admin-saas/src/index.css`;
- `frontend/admin-saas/tailwind.config.js`;
- `frontend/admin-saas/src/routes/AdminSaasDashboard.tsx`.

Los botones rápidos del dashboard apuntan al Django Admin nativo para evitar
que el operador regrese accidentalmente a una interfaz administrativa legada.

## Formularios y permisos

`core/admin.py` usa `unfold.admin.ModelAdmin` y los inlines de Unfold. Las
reglas de permisos continúan en `TradeFlowPermissionMixin`; el cambio visual
no concede acceso adicional ni modifica la lógica de negocio.

Los formularios de usuarios utilizan las variantes de Unfold para conservar
el estilo de campos y contraseñas. La protección de superusuarios y las reglas
del administrador de demostración permanecen sin cambios.

## Mantenimiento

Al agregar una sección administrativa:

1. Registrar el modelo con `TradeFlowModelAdmin`.
2. Añadir el destino a `UNFOLD['SIDEBAR']['navigation']` si requiere acceso
   persistente.
3. Mantener el texto de interfaz en inglés.
4. No crear una nueva cabecera, barra lateral o contenedor de ancho limitado.
5. Ejecutar las pruebas de navegación, diseño y permisos.

Las suites principales son:

- `core/tests/test_tradeflow_admin_navigation.py`;
- `core/tests/test_tradeflow_admin_layout.py`;
- `core/tests/test_tradeflow_admin_site.py`;
- `core/tests/test_gdpr_owasp_followup.py`.
