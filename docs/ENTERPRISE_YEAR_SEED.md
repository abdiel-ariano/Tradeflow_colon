# Simulación de 1 año operativo (enterprise seed)

Comando: `python manage.py seed_enterprise_year`

Persiste en **PostgreSQL / Supabase** mediante el ORM de Django (sin datos mock en frontend).

## Marcadores (para `--clear` y soporte)

| Entidad   | Criterio |
|-----------|----------|
| Empresas  | RUC con prefijo `8-1Y-SIM-` |
| Órdenes   | `order_number` con prefijo `TF-1YSIM-` |
| Usuarios  | `username` con prefijo `sim1y_` |
| Home CMS  | `HomePromoSection.slug` con prefijo `eyear-` |

## Escalas

- **demo**: pocas empresas y órdenes (adecuado para CI o SQLite rápido).
- **standard**: volumen representativo (miles de productos en conjunto con stress).
- **stress**: muchas empresas, miles de productos y miles de líneas de pedido.

## Ejemplos

```bash
# Producción / staging con Supabase (recomendado borrar simulación previa)
python manage.py seed_enterprise_year --clear --scale=standard

# Sin descarga de imágenes (más rápido)
python manage.py seed_enterprise_year --clear --scale=standard --skip-images

# Semilla fija para demos reproducibles
python manage.py seed_enterprise_year --clear --scale=demo --seed=7 --skip-images
```

## Requisitos

- Migraciones aplicadas (incluye tablas enterprise: ads, logística, SaaS).
- `bootstrap_saas_datastore` en estado sano (planes activos, migración checkout si aplica).
- Opcional: correo real para el resto de la plataforma — ver [ENTERPRISE_EMAIL.md](./ENTERPRISE_EMAIL.md).

## Notas

- El comando **no** envía correos; solo escribe en base de datos.
- En bases mixtas (demo real + simulación), `--clear` solo elimina filas con los prefijos anteriores.
