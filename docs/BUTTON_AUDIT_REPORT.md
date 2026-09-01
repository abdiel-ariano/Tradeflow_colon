# TradeFlow — Auditoría de botones por rol

Fecha: 2026-09-01  
Entrega objetivo: **4 de septiembre de 2026**

## Metodología

1. **Tests automatizados Django** (`core/tests/test_role_button_audit.py`)
   - Guest, buyer, seller, admin
   - GET de páginas principales (sin error 5xx)
   - POST de acciones tipo botón: carrito, logout, idioma, cotización

2. **Auditoría live** (`scripts/live_button_audit.py`)
   - Servidor local con `cargar_demo`
   - Login real con `demo_buyer`, `demo_seller`, `demo_admin`
   - 28 rutas verificadas sin errores de servidor

3. **CI subset** — 99 tests OK incluyendo flujo compra, PWA, onboarding, seguridad

## Credenciales demo

| Rol | Usuario | Clave |
|-----|---------|-------|
| Comprador | `demo_buyer` | `Demo1234!` |
| Vendedor | `demo_seller` | `Demo1234!` |
| Admin | `demo_admin` | `Demo1234!` |

## Pantallas auditadas

### Guest (público)
`/`, `/catalogo/`, `/login/`, `/signup/comprador/`, `/carrito/`, `/mapa/`, `/acerca/`, `/verified-suppliers/`, `/deals/`, PDP producto, legal, marketplace

### Buyer
`/perfil/`, `/mis-ordenes/`, `/mis-cotizaciones/`, `/checkout/`, `/carrito/`, agregar carrito, cotización automática, logout, cambio idioma

### Seller
Portal completo `/mi-tienda/*`: productos, ventas, plan, cotizaciones, configuración, balances, clientes, impuestos, QR, insights, logout

### Admin
`/dashboard/`, `/saas/`, `/productos/`, `/ordenes/`, `/empresas/`, `/panel/applications/`, logout

## Resultado

| Auditoría | Checks | Fallos |
|-----------|--------|--------|
| Django tests | 7 casos | **0** |
| Live server | 28 rutas | **0** |
| CI subset | 99 tests | **0** |

**No se detectaron botones que devuelvan error 500** en las rutas auditadas.

## Cómo re-ejecutar

```bash
python manage.py test core.tests.test_role_button_audit -v2
python manage.py runserver 0.0.0.0:8000   # otra terminal
python scripts/live_button_audit.py
```

## Pendiente manual (recomendado antes del 4/09)

- Verificación visual en móvil (navbar hamburger, carrito AJAX)
- Botón PWA Install (solo aparece con `beforeinstallprompt`)
- OAuth Google/Microsoft en login/signup
- Flujos MFA staff (`/staff-mfa/`)
