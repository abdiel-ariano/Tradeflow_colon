# Migración de base de datos: Supabase Postgres → AWS RDS

**Proyecto:** TradeFlow Colón (marketplace B2B ZLC)  
**Prioridad:** **P0** — Mejora agosto–septiembre 2026  
**Disparador:** el tier gratuito de Supabase se cierra / pausa el **1 de agosto de 2026**  
**Fecha del plan:** 6 de agosto de 2026  
**Alcance P0:** solo la base de datos. Storage de imágenes permanece en Supabase de forma temporal; la app permanece en Railway.  
**Estado:** planificado — ejecución inmediata (ventana de corte 15–30 min).

---

## 0. Por qué esto es P0 ahora

TradeFlow **no corre en Supabase**: Django está en Railway. Supabase solo aporta Postgres (`DATABASE_URL`) y Storage de medios. Si el proyecto free se pausa o se pierde el acceso el 1 ago:

| Qué se rompe | Impacto |
|---|---|
| Postgres inaccesible | Login, catálogo, carrito, órdenes, admin — **plataforma caída** |
| Storage pausado (si el proyecto queda inactivo tras sacar la DB) | Imágenes del catálogo caídas |

**Acción inmediata (hoy):** abrir el dashboard de Supabase y comprobar si el proyecto está **Active**, **Paused** o **Restricted**. Si está pausado, restaurarlo antes de cualquier dump. Si aún hay acceso, hacer un `pg_dump` de respaldo **antes** de crear RDS.

---

## 1. Resumen ejecutivo

| Ítem | Decisión |
|---|---|
| Destino | **AWS RDS PostgreSQL** `db.t4g.micro`, región `us-east-1` |
| Método | `pg_dump` / `pg_restore` (dump frío; DB pequeña, sin DMS) |
| Código Django | **Cero cambios** — solo `DATABASE_URL` + limpieza de env en Railway |
| Ventana de corte | 15–30 minutos |
| Costo RDS | ~$16–22 USD/mes |
| App host | Railway (sin mover) |
| Storage | Sigue en Supabase → migrar a S3 en septiembre (P1) |

Django usa ORM estándar. El normalizador `core/utils/database_url.py` solo reescribe hosts `pooler.supabase.com`; una URL de RDS pasa intacta.

---

## 2. Roadmap agosto–septiembre (P0 → P1)

```
AGOSTO (P0 — DB viva o recuperada)
├── Día 0   Verificar estado Supabase + dump de emergencia
├── Día 1   Crear RDS + security group + force_ssl
├── Día 1–2 Ensayo en frío (dump → restore → check_database)
└── Día 2–3 Corte producción (cambiar DATABASE_URL en Railway)

SEPTIEMBRE (P1 — salir de Supabase)
├── Semana 1–2  Storage → S3 + CloudFront
├── Semana 3    Quitar SUPABASE_* de Railway; limpiar código
└── Semana 4    Cerrar / borrar proyecto Supabase
```

**No** migrar la app a AWS en este ciclo salvo créditos Activate ya aprobados y razón operativa concreta.

---

## 3. Arquitectura actual (verificada en el código)

| Componente | Proveedor actual | Archivo/configuración |
|---|---|---|
| App Django 6 | Railway (Docker + gunicorn, 2 workers) | `railway.json`, `Dockerfile` |
| PostgreSQL | Supabase (pooler `aws-0-us-east-1.pooler.supabase.com`) | `DATABASE_URL` → `tradeflow_colon/settings.py` |
| Imágenes | Supabase Storage (bucket `media`, público) | `core/storage/supabase_media.py` |
| Auth | Django + allauth — **no** Supabase Auth | `AUTHENTICATION_BACKENDS` |
| Email | Resend — **no** Edge Function en producción | `core/email_service.py` |
| Realtime seller | Supabase Realtime **opcional**; fallback polling 5s | `static/js/seller_portal.js` |
| Cache | Redis opcional | `REDIS_URL` |
| CDN / DNS | Cloudflare → Railway | — |

### Acoplamiento real con Supabase

1. **`DATABASE_URL`** — lo que migramos (P0).
2. **Storage** — no se toca en P0; obligatorio en P1 (septiembre).
3. **`core/supabase_client.py`** — URLs firmadas; bucket público → casi no se usa.
4. **Realtime** — al sacar la DB de Supabase, `postgres_changes` deja de disparar; el portal vendedor **sigue funcionando por polling**. Sin bloqueador.
5. **Artefactos muertos** — Edge Function de email y SQL `supabase/migrations/..._marketplace_cart.sql` (tablas huérfanas). No se migran; se limpian después.

Las URLs de imagen se arman en runtime desde settings; los modelos guardan solo la ruta. Mover la DB no rompe imágenes; mover Storage después no rompe la DB.

---

## 4. Trampa del Storage residual (leer antes del corte)

Tras el corte P0, Supabase queda solo para imágenes:

- **Plan free:** riesgo alto de **pausa por inactividad** → catálogo sin imágenes.
- **Plan Pro ($25/mes):** doble factura (RDS + Supabase) solo por Storage.

**Regla:** no pausar ni borrar Supabase hasta terminar P1 (S3). Agendar Storage en las **2–4 semanas** posteriores al corte DB (septiembre).

---

## 5. Pros / contras (solo DB)

**Pros:** backups PITR 7 días, cero código, rollback en minutos, camino a créditos AWS / compliance, métricas CloudWatch.

**Contras:** se pierde el SQL editor de Supabase; ~$16–22/mes extra mientras Storage siga ahí; app en Railway + DB en AWS (RDS **públicamente accesible** + TLS + SG).

---

## 6. Runbook de migración

### Fase 0 — Decisiones y rescate (antes de gastar)

1. **Estado Supabase YA:** Active / Paused / Restricted. Si Paused → Restore Project, luego dump.
2. **Dump de emergencia** (aunque el corte sea mañana):

   ```bash
   pg_dump "postgresql://postgres:PASSWORD@db.TU_REF.supabase.co:5432/postgres" \
     -n public --no-owner --no-privileges -Fc -f tradeflow-emergency.dump
   ```

   Host **directo** `db.<ref>.supabase.co`, **nunca** el pooler.
3. **AWS Activate** si aplica (antes de crear recursos).
4. **Región `us-east-1`** (misma que el pooler actual).
5. Versión Postgres y tamaño:

   ```sql
   SELECT version();
   SELECT pg_size_pretty(pg_database_size('postgres'));
   ```

   RDS ≥ misma major. Con decenas de MB, dump frío basta (sin DMS).

### Fase 1 — Crear RDS

| Parámetro | Valor | Motivo |
|---|---|---|
| Motor | PostgreSQL (misma major o superior) | dump/restore compatible |
| Instancia | `db.t4g.micro` | 2 workers gunicorn; ~$13/mes |
| Storage | gp3, 20 GB | mínimo gp3 |
| Multi-AZ | No | costo; sin tráfico prod real aún |
| Backups | 7 días | PITR |
| Deletion protection | Sí | anti-borrado accidental |
| Publicly accessible | Sí | app en Railway fuera de la VPC |
| DB name | `postgres` | igual que Supabase |

**Seguridad obligatoria (RDS público):**

1. Parameter group: `rds.force_ssl = 1`
2. Password larga **sin** `@ : / #`
3. Security group 5432: IPs estáticas de Railway si existen; si no, `0.0.0.0/0` + TLS + password fuerte (deuda a cerrar al mover la app a AWS)

**Costo:** ~$16–22 USD/mes.

### Fase 2 — Ensayo en frío

Requisito: `pg_dump` / `pg_restore` PostgreSQL 16+.

```bash
# Dump (solo schema public — excluye auth/storage/realtime de Supabase)
pg_dump "postgresql://postgres:PASSWORD@db.TU_REF.supabase.co:5432/postgres" \
  -n public --no-owner --no-privileges -Fc -f tradeflow.dump

# Restore
pg_restore --no-owner --no-privileges \
  -d "postgresql://postgres:PASSWORD@TU-INSTANCIA.xxxxx.us-east-1.rds.amazonaws.com:5432/postgres" \
  tradeflow.dump
```

Validación local apuntando `.env` a RDS:

```bash
python manage.py check_database
python manage.py migrate --check
python manage.py verify_integrations
```

Comparar conteos: usuarios, empresas, productos, órdenes. Cronometrar dump+restore → define ventana Fase 3.

### Fase 3 — Corte producción (15–30 min)

1. Snapshot manual RDS + conservar dump del ensayo.
2. Hora de mínimo tráfico (`DatabaseUnavailableMiddleware` muestra mantenimiento si alguien entra).
3. Limpiar base de ensayo en RDS (drop/recreate `postgres`).
4. Dump final + restore. Tras el dump final, datos en Supabase = congelados.
5. **Railway → Variables:**

   | Acción | Variable | Motivo |
   |---|---|---|
   | Actualizar | `DATABASE_URL` | → RDS |
   | **Eliminar** | `SUPABASE_DB_HOST`, `SUPABASE_DB_PASSWORD`, `SUPABASE_DB_PORT`, `SUPABASE_PROJECT_REF` | si `DATABASE_URL` falla, el fallback **reconstruye Supabase en silencio** |
   | **Eliminar** | `DATABASE_PASSWORD` (si existe) | pisa la password de la URL |
   | Mantener | `DB_SSL=true`, `DB_SSLMODE=require` | obligatorio con `force_ssl` |
   | **Mantener** | `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `SUPABASE_ANON_KEY`, `SUPABASE_STORAGE_BUCKET` | Storage aún depende de ellas |

6. Redeploy. `docker-entrypoint.sh` corre `check_database` + `migrate`; fallo de RDS **aborta sin tumbar** la versión anterior.
7. Smoke: login, catálogo (imágenes desde Supabase), carrito, checkout, admin, `/health/ready/`.
8. **Rollback:** revertir `DATABASE_URL` a Supabase + redeploy. Solo es trivial si **nadie escribió en RDS** tras el corte.

### Fase 4 — Post-corte (primera semana de agosto)

1. Alarmas CloudWatch: CPU > 80 %, conexiones > 40, free storage < 5 GB.
2. No hace falta RDS Proxy (~2–4 conexiones con 2 workers).
3. **No pausar Supabase** — Storage.
4. Opcional: `DROP TABLE products, cart_items;` (huérfanas del frontend React viejo).
5. Si Analytics usa hosts externos: añadir host RDS a `ANALYTICS_DB_HOST_ALLOWLIST`.
6. Agendar P1 Storage → S3.

---

## 7. Matriz de riesgos

| Riesgo | Prob. | Impacto | Mitigación |
|---|---|---|---|
| Proyecto free ya pausado / sin acceso (post 1 ago) | Alta | Crítico | Restaurar proyecto; dump emergencia; si no hay restore, usar último backup local / Railway logs |
| Supabase pausado por inactividad post-corte → imágenes caídas | Media | Alto | P1 Storage en 2–4 semanas; vigilar estado del proyecto |
| Fallback silencioso a Supabase por env residual | Media | Alto | Borrar `SUPABASE_DB_*` y `DATABASE_PASSWORD` en el mismo cambio |
| Escrituras en RDS antes de detectar fallo | Baja | Alto | Ventana corta; go/no-go en 15 min |
| RDS público en internet | Alta (diseño) | Medio | `force_ssl`, password fuerte, SG restringido |
| Realtime seller deja de pushear | Alta | Bajo | Polling 5s ya es el camino principal |

---

## 8. Qué NO cambia en P0

- Código de aplicación (cero diffs obligatorios).
- Dominio, DNS, Cloudflare, certificados.
- Storage, OAuth, email Resend, cron de suscripciones.
- Latencia percibida (misma región AWS).
- Portal vendedor (sigue por polling).

---

## 9. Trabajo futuro (orden)

1. **P1 sept — Storage → S3 + CloudFront** (elimina dependencia y factura Supabase).
2. Limpieza: `core/supabase_client.py`, `core/storage/supabase_media.py`, dir `supabase/`, workflow `deploy-supabase-functions.yml`, dep `supabase` en `requirements.txt`.
3. App Railway → AWS (Elastic Beanstalk / ECS) **solo** con tráfico real post-Expo, cliente enterprise, o créditos Activate.

---

## 10. Checklist operativo (imprimible)

- [ ] Supabase: proyecto Active (o restaurado)
- [ ] Dump emergencia en disco seguro
- [ ] Cuenta AWS + región us-east-1
- [ ] `SELECT version()` / tamaño DB
- [ ] RDS creado (`t4g.micro`, public, force_ssl, deletion protection)
- [ ] Ensayo frío OK (`check_database`, `migrate --check`, conteos)
- [ ] Snapshot RDS + dump final
- [ ] Railway: `DATABASE_URL` → RDS; borrar `SUPABASE_DB_*` / `DATABASE_PASSWORD`; conservar `SUPABASE_*` de Storage
- [ ] Redeploy + smoke test
- [ ] CloudWatch alarms
- [ ] Ticket P1: Storage → S3 (septiembre)
