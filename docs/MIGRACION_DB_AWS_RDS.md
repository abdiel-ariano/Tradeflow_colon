# Migración de base de datos: Supabase Postgres → AWS RDS

**Proyecto:** TradeFlow Colón (marketplace B2B ZLC)
**Fecha del análisis:** 29 de julio de 2026
**Alcance decidido:** solo la base de datos. El Storage de imágenes permanece en Supabase por ahora; la aplicación permanece en Railway.
**Estado:** planificado, pendiente de ejecución.

---

## 1. Resumen ejecutivo

TradeFlow Colón **no vive en Supabase**: la aplicación Django corre en Railway (contenedor Docker con gunicorn). Supabase provee únicamente dos servicios:

1. **PostgreSQL** — la base de datos, conectada vía la variable de entorno `DATABASE_URL`.
2. **Storage** — las imágenes de productos, vía API compatible con S3.

Esta migración mueve **solo el punto 1** a AWS RDS. Es un cambio de **cero líneas de código**: todo se resuelve con variables de entorno y una copia de datos, porque Django usa su ORM estándar sin ninguna característica propietaria de Supabase.

**Duración estimada de la ventana de corte:** 15–30 minutos.
**Costo mensual estimado de RDS:** $16–22 USD.
**Riesgo principal:** dejar el Storage en Supabase crea una dependencia residual que hay que resolver en semanas, no meses (ver sección 3).

---

## 2. Arquitectura actual (verificada en el código)

| Componente | Proveedor actual | Archivo/configuración relevante |
|---|---|---|
| Aplicación Django 6 | Railway (Docker + gunicorn, 2 workers) | `railway.json`, `Dockerfile`, `scripts/docker-entrypoint.sh` |
| Base de datos PostgreSQL | Supabase (vía pooler `aws-0-us-east-1.pooler.supabase.com`) | `DATABASE_URL` en `tradeflow_colon/settings.py:160` |
| Imágenes de productos | Supabase Storage (bucket `media`, público) | `core/storage/supabase_media.py` |
| Autenticación de usuarios | Django + allauth (Google/Microsoft/LinkedIn) — **no** usa Supabase Auth | `settings.py` (AUTHENTICATION_BACKENDS) |
| Email transaccional | Resend — **no** usa Supabase | `core/email_service.py` |
| Cache | Redis opcional / memoria local | `REDIS_URL` en settings |
| CDN / DNS | Cloudflare delante de Railway | `scripts/purge_cloudflare_cache.sh` |
| Cron diario | Railway Cron (`process_seller_subscriptions`) | documentado en `.env.example` |

### Puntos de acoplamiento con Supabase (los únicos que existen)

1. **`DATABASE_URL`** — conexión Postgres estándar. El normalizador `core/utils/database_url.py` tiene lógica especial para el pooler de Supabase, pero **una URL de RDS pasa intacta** (la reescritura solo se activa con hosts `pooler.supabase.com`). Verificado.
2. **Storage de medios** (`core/storage/supabase_media.py`) — no se toca en esta migración.
3. **Cliente Supabase** (`core/supabase_client.py`) — solo genera URLs firmadas para buckets privados; el bucket es público, así que en la práctica no se usa. No se toca.
4. **Artefactos muertos** — la Edge Function `supabase/functions/send-transactional-email/` no la invoca ningún código Python (el email real va por Resend), y el SQL `supabase/migrations/20260707000000_marketplace_cart.sql` crea tablas huérfanas de un frontend React abandonado. Ninguno se migra; se limpian después.

**Conclusión de la auditoría:** las URLs de imágenes se construyen dinámicamente en cada request desde settings — los modelos guardan solo la ruta del archivo. No hay URLs de Supabase congeladas en la base de datos, por lo que mover la DB no afecta las imágenes, y mover las imágenes después no afectará la DB.

---

## 3. Advertencia importante: la trampa del Storage residual

Migrar solo la DB deja el proyecto Supabase vivo únicamente para servir imágenes. Esto tiene dos consecuencias según el plan contratado:

- **Plan gratuito:** Supabase **pausa proyectos inactivos**. Al sacar la base de datos, la actividad del proyecto cae casi a cero. Si Supabase lo pausa, **se caen las imágenes de todos los productos del catálogo**. Este es un riesgo real y silencioso.
- **Plan Pro ($25/mes):** se sigue pagando la factura completa de Supabase solo por hospedar imágenes, **además** de la nueva factura de RDS. Después de la migración se paga más que hoy.

**Mitigación obligatoria:** agendar la migración del Storage a S3 + CloudFront dentro de las **4–6 semanas** posteriores al corte de la DB. Mientras tanto, **no pausar ni borrar el proyecto Supabase** bajo ninguna circunstancia.

---

## 4. Pros y contras de esta migración (solo DB)

### Pros

- **Backups reales:** RDS ofrece point-in-time recovery de 7 días y snapshots manuales, superior al tier bajo de Supabase.
- **Cambio mínimo:** cero código; solo variables de entorno y copia de datos. Rollback en minutos.
- **Camino a AWS:** primer paso concreto si se busca elegibilidad de créditos AWS Activate o requisitos de compliance de un cliente/inversionista.
- **Métricas:** CloudWatch da visibilidad de CPU, conexiones y almacenamiento que el panel gratuito de Supabase no iguala.

### Contras

- **Se pierde el dashboard de Supabase** (editor SQL visual, vista de tablas, logs con un clic). En RDS todo es consola AWS o cliente `psql`.
- **Costo adicional** de $16–22/mes mientras el Storage siga en Supabase (posible doble factura, ver sección 3).
- **Arquitectura partida en dos proveedores** (Railway + AWS): dos facturas, dos consolas, y la conexión app→DB cruza internet público (mitigado con TLS forzado; ambos están en us-east-1 así que la latencia no cambia).
- **RDS debe ser públicamente accesible** porque la app vive en Railway, fuera de la VPC de AWS. No es lo ideal en seguridad; se compensa con TLS obligatorio y firewall (detalle en Fase 1).

---

## 5. Runbook de migración

### Fase 0 — Decisiones previas (antes de gastar un dólar)

1. **Aplicar a AWS Activate** (créditos para startups) antes de crear recursos.
2. **Región: `us-east-1`.** El pooler actual de Supabase ya está ahí (`aws-0-us-east-1.pooler.supabase.com`), así que la latencia desde Railway no cambia.
3. **Averiguar la versión de Postgres actual.** En Supabase → SQL Editor:

   ```sql
   SELECT version();
   ```

   RDS debe crearse con la **misma versión mayor o superior** (ej.: Supabase en PG 15 → RDS PG 15, 16 o 17). Nunca menor.
4. **Medir el tamaño de la base** para estimar la ventana de corte:

   ```sql
   SELECT pg_size_pretty(pg_database_size('postgres'));
   ```

   Con el volumen actual (pre-lanzamiento) se esperan decenas de MB → el dump/restore toma minutos. Por eso **no** se necesita AWS DMS ni replicación continua; un dump frío es suficiente y mucho más simple.

### Fase 1 — Crear la instancia RDS

Configuración recomendada:

| Parámetro | Valor | Por qué |
|---|---|---|
| Motor | PostgreSQL (versión según Fase 0) | compatibilidad de dump/restore |
| Instancia | `db.t4g.micro` | suficiente para 2 workers gunicorn; ~$13/mes |
| Storage | gp3, 20 GB | mínimo de gp3; sobra para años al ritmo actual |
| Multi-AZ | **No** | duplica el costo; innecesario sin tráfico de producción real |
| Backups automáticos | 7 días | point-in-time recovery |
| Deletion protection | **Sí** | evita borrado accidental desde la consola |
| Publicly accessible | **Sí** | la app está en Railway, fuera de la VPC — no hay alternativa sin migrar la app |
| Nombre de la base | `postgres` | igual que Supabase; evita tocar el path de `DATABASE_URL` |

**Compensaciones de seguridad por ser públicamente accesible (obligatorias):**

1. En el *parameter group*: `rds.force_ssl = 1` — rechaza cualquier conexión sin TLS.
2. Contraseña larga generada aleatoriamente, **sin** los caracteres `@ : / #` (el parser de la app los maneja, pero eliminarlos evita una fuente clásica de errores de conexión).
3. Security group: entrada al puerto 5432 restringida a las **IPs de egreso estáticas de Railway** si el plan de Railway las ofrece (verificar en Railway → Settings → Networking). Si el plan no tiene IPs estáticas, se abre `0.0.0.0/0` — aceptable con TLS forzado + contraseña fuerte, pero conviene registrar esto como deuda de seguridad a cerrar cuando la app migre a AWS.

**Costo estimado total: $16–22 USD/mes** (instancia + storage + backups).

### Fase 2 — Ensayo en frío (sin tocar producción)

Objetivo: validar el proceso completo de copia **antes** del día del corte, contra la base de producción real pero sin interrumpirla.

Requisito: tener `pg_dump` y `pg_restore` de PostgreSQL 16+ instalados localmente.

**Paso 2.1 — Dump desde Supabase:**

```bash
pg_dump "postgresql://postgres:PASSWORD@db.TU_REF.supabase.co:5432/postgres" -n public --no-owner --no-privileges -Fc -f tradeflow.dump
```

Explicación de cada flag (importan todos):

- **Host directo `db.<ref>.supabase.co`, no el pooler** — el pooler en modo transacción rompe `pg_dump` (necesita una sesión persistente).
- **`-n public`** — copia solo el esquema `public`, donde viven todas las tablas de Django (`core_*`, `auth_*`, `django_*`). Excluye los esquemas internos de Supabase (`auth`, `storage`, `realtime`, `extensions`) que **no deben** existir en RDS y cuyo dump fallaría por permisos.
- **`--no-owner --no-privileges`** — omite propietarios y grants ligados a roles de Supabase (`supabase_admin`, `service_role`, `anon`) que no existen en RDS. Sin estos flags el restore escupe cientos de errores.
- **`-Fc`** — formato comprimido custom, requerido por `pg_restore`.

Nota: las tablas huérfanas `products` y `cart_items` (del SQL viejo de un frontend abandonado) vendrán incluidas en la copia. Son inofensivas; se limpian en la Fase 4.

**Paso 2.2 — Restore hacia RDS:**

```bash
pg_restore --no-owner --no-privileges -d "postgresql://postgres:PASSWORD@TU-INSTANCIA.xxxxx.us-east-1.rds.amazonaws.com:5432/postgres" tradeflow.dump
```

**Paso 2.3 — Validación con la propia app.** Apuntar el `.env` local a RDS (`DATABASE_URL=` la URL de RDS) y correr:

```bash
python manage.py check_database
```

```bash
python manage.py migrate --check
```

```bash
python manage.py verify_integrations
```

- `check_database` confirma conectividad y credenciales.
- `migrate --check` confirma que el esquema copiado está exactamente al día con las migraciones del código (debe decir que no hay migraciones pendientes; si dice lo contrario, el dump está incompleto o desactualizado).
- Adicionalmente, comparar conteos de filas entre Supabase y RDS en las tablas críticas: usuarios, empresas, órdenes, productos.

**Paso 2.4 — Cronometrar.** Anotar cuánto tardó dump + restore. Ese tiempo (más margen) define la ventana de corte de la Fase 3.

### Fase 3 — Corte de producción (ventana de 15–30 minutos)

1. **Snapshot manual de RDS** y conservar el dump del ensayo. Doble red de seguridad.
2. **Elegir hora de mínimo tráfico.** Si algún usuario entra durante el lapso, el middleware `DatabaseUnavailableMiddleware` de la app muestra una página de mantenimiento en lugar de un error crudo.
3. **Limpiar la base de ensayo en RDS** (borrar y recrear la base `postgres` de la instancia) para que el restore final entre en una base vacía y no se mezclen datos del ensayo con los finales.
4. **Dump final + restore** con los mismos comandos de la Fase 2. A partir del dump final, considerar los datos de Supabase congelados.
5. **Cambiar variables en Railway → Variables:**

   | Acción | Variable | Motivo |
   |---|---|---|
   | Actualizar | `DATABASE_URL` | apuntar a RDS |
   | **Eliminar** | `SUPABASE_DB_HOST`, `SUPABASE_DB_PASSWORD`, `SUPABASE_DB_PORT`, `SUPABASE_PROJECT_REF` | si `DATABASE_URL` quedara vacía por error, el fallback de `core/utils/database_url.py` **reconstruiría silenciosamente la URL de Supabase** con estas variables — la app arrancaría contra la base vieja sin avisar |
   | **Eliminar** | `DATABASE_PASSWORD` (si existe) | sobreescribe la contraseña embebida en `DATABASE_URL`; con RDS pisaría la contraseña correcta |
   | Mantener | `DB_SSL=true`, `DB_SSLMODE=require` | funcionan igual con RDS y son obligatorias con `rds.force_ssl=1` |
   | **Mantener** | `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `SUPABASE_ANON_KEY`, `SUPABASE_STORAGE_BUCKET` | ¡el Storage de imágenes sigue en Supabase! Quitarlas rompería todas las imágenes |

6. **Redeploy.** El `scripts/docker-entrypoint.sh` corre automáticamente el preflight `check_database` y luego `migrate`; si la conexión a RDS falla, **aborta el deploy sin romper nada** (la versión anterior sigue corriendo).
7. **Smoke test manual:** login, catálogo (verificar que las imágenes cargan — deben seguir viniendo de Supabase Storage), agregar al carrito, checkout, Django Admin, y el endpoint `/health/ready/`.
8. **Rollback si algo falla:** revertir `DATABASE_URL` a la URL de Supabase y redeploy. Por eso la ventana debe ser corta y con tráfico pausado: la condición del rollback es que **nada se haya escrito en RDS que Supabase no tenga**. Una vez que usuarios reales escriben en RDS, el rollback ya implica pérdida de datos y deja de ser trivial.

### Fase 4 — Post-corte (primera semana)

1. **Alarmas CloudWatch:** CPU > 80 %, conexiones > 40, storage libre < 5 GB, memoria liberable baja. Notificación por email (SNS).
2. **Conexiones:** con 2 workers gunicorn y `conn_max_age=600` la app mantiene ~2–4 conexiones persistentes, muy lejos del límite (~80) de `db.t4g.micro`. **No** se necesita RDS Proxy ni PgBouncer hasta escalar workers significativamente.
3. **No pausar ni borrar el proyecto Supabase** — el Storage depende de él (sección 3). Agendar la migración del Storage a S3 + CloudFront en las próximas 4–6 semanas.
4. **Limpieza de tablas huérfanas** en RDS (opcional, cuando convenga): `DROP TABLE products, cart_items;` — son restos del frontend React abandonado; Django no las usa.
5. **Limpieza cosmética de código** (no urgente, pero engañosa si no se hace): los textos de ayuda de `python manage.py check_database` y de `database_connection_hint()` en `core/utils/database_url.py` siguen diciendo "Supabase → Settings → reset database password". Quien depure un fallo de conexión contra RDS recibirá instrucciones equivocadas.
6. **Analytics:** si el staff usa la función de Analytics con fuentes de datos externas, añadir el host de RDS a `ANALYTICS_DB_HOST_ALLOWLIST`.
7. El flag interno `USING_SUPABASE` en settings seguirá evaluando `True` (también se activa con cualquier engine Postgres). Sin efectos colaterales; se renombra en la limpieza cosmética.

---

## 6. Matriz de riesgos

| Riesgo | Probabilidad | Impacto | Mitigación |
|---|---|---|---|
| Proyecto Supabase pausado por inactividad → imágenes caídas | Media (plan free) | Alto | Migrar Storage en 4–6 semanas; mientras tanto vigilar el estado del proyecto |
| Fallback silencioso a la URL de Supabase por variables residuales | Media | Alto | Eliminar `SUPABASE_DB_*` y `DATABASE_PASSWORD` en el mismo cambio que `DATABASE_URL` |
| Escrituras en RDS antes de detectar un problema → rollback con pérdida | Baja | Alto | Ventana corta, smoke test inmediato, decisión go/no-go en los primeros 15 min |
| RDS público expuesto a internet | Alta (es por diseño) | Medio | `rds.force_ssl=1`, contraseña fuerte, security group restringido si Railway da IPs estáticas |
| Versión de Postgres incompatible | Baja | Medio | Verificar versión en Fase 0; el ensayo en frío la detecta de todos modos |
| Error de configuración AWS con costo inesperado | Media | Bajo-Medio | Solo se crea RDS (sin NAT, sin VPC endpoints); alarma de billing a $30/mes |

---

## 7. Qué NO cambia con esta migración

- El código de la aplicación: **cero cambios**.
- El dominio, DNS, Cloudflare, certificados.
- El Storage de imágenes (sigue en Supabase temporalmente).
- El login de usuarios, OAuth, email, cron de suscripciones.
- La latencia percibida por los usuarios (misma región AWS).

## 8. Trabajo futuro (fuera de este alcance, en orden recomendado)

1. **Storage → S3 + CloudFront** (4–6 semanas después del corte; elimina la dependencia y la factura de Supabase).
2. Limpieza de código: borrar `core/supabase_client.py`, `core/storage/supabase_media.py`, el directorio `supabase/`, el workflow `deploy-supabase-functions.yml` y la dependencia `supabase` de `requirements.txt`.
3. Evaluar migrar la app de Railway a AWS (App Runner) **solo** cuando exista una razón operativa concreta: tráfico real post-Expo, requisito de cliente enterprise, o créditos Activate aprobados.
