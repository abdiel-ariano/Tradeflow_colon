# Migración P0: Supabase y Railway → AWS

**Proyecto:** TradeFlow Colón  
**Fecha de verificación:** 7 de agosto de 2026  
**Fecha límite externa:** 12 de agosto de 2026  
**Objetivo temporal:** operar sin pagos nuevos hasta el 30 de septiembre de 2026  
**Estado:** preparación técnica; producción todavía no ha cambiado.

## 1. Decisión vigente

Railway Pro no está disponible. Por tanto, PostgreSQL no se publicará en
Internet para permitir conexiones desde Railway. El traslado seguro incluye
la aplicación y la base de datos:

```text
Cloudflare
    │
    ▼
EC2 (Docker, Django y Nginx)
    ├── grupo de seguridad → RDS PostgreSQL 17 privado
    ├── instance profile → S3 media privado
    └── respaldos lógicos cifrados en S3
```

No se utiliza NAT Gateway, balanceador, bastion host ni dirección pública para
RDS. El acceso administrativo a EC2 se realiza con AWS Systems Manager, sin
abrir SSH.

## 2. Inventario verificado en producción

| Elemento | Resultado |
|---|---:|
| PostgreSQL | 17.6 |
| Tamaño total | 18 MB |
| Usuarios Django (`public.auth_user`) | 99 |
| Usuarios Supabase Auth (`auth.users`) | 0 |
| Empresas | 18 |
| Productos | 1,333 |
| Órdenes | 918 |
| Pagos | 850 |
| Eventos logísticos | 3,177 |
| Buckets de Supabase Storage | 0 |
| Objetos de Supabase Storage | 0 |

TradeFlow autentica con Django y `django-allauth`; no depende de Supabase Auth.
Los registros de productos contienen rutas bajo `productos/`, pero no existen
objetos en Supabase Storage. Por tanto, esta migración no tiene archivos
históricos de Storage que copiar. Las nuevas cargas de vendedores se guardan
en un bucket S3 privado; las rutas históricas sin objeto deben regenerarse o
dejarse vacías para usar el SVG de respaldo.

Las extensiones instaladas son `pg_stat_statements`, `pgcrypto`, `plpgsql`,
`supabase_vault` y `uuid-ossp`. Ninguna columna de `public` tiene valores por
defecto que dependan de Vault o de funciones exclusivas de Supabase. La función
`public.rls_auto_enable()` sí es exclusiva de Supabase y se elimina después de
restaurar.

## 3. Control de costo

La cuenta dispone de USD 120 en créditos con vencimiento el 6 de agosto de
2027. Para este periodo se utilizarán los tamaños mínimos:

| Recurso | Configuración inicial |
|---|---|
| EC2 | `t3.micro`, 20 GiB gp3 |
| RDS | PostgreSQL 17, `db.t4g.micro`, 20 GiB gp3, Single-AZ, respaldos automáticos desactivados en AWS Free Plan |
| S3 | buckets separados para respaldo y media; versionado, AES-256 y acceso público bloqueado |
| ECR | máximo de diez imágenes conservadas |

El objetivo es consumir aproximadamente USD 25–35 por mes en créditos. El
presupuesto de AWS es una alerta y no un bloqueo. La cuenta debe permanecer en
**Free plan**; no debe actualizarse a Paid plan durante este periodo.

## 4. Archivos de esta implementación

| Archivo | Función |
|---|---|
| `infra/aws/p0-stack.yaml` | VPC, EC2, RDS privado, S3, ECR, SSM, alarmas y rol OIDC de GitHub |
| `.github/workflows/deploy-aws-staging.yml` | Compilación manual y despliegue sin credenciales AWS permanentes |
| `scripts/aws/configure_media_runtime.sh` | Activa S3 en la instancia existente, valida y revierte si falla |
| `scripts/aws/export_supabase.sh` | Dump privado de `public`, conteos y SHA-256 |
| `scripts/aws/restore_rds.sh` | Restauración abortable únicamente sobre una base vacía |
| `scripts/aws/verify_migration.sh` | Comparación exacta de tablas críticas |
| `scripts/aws/critical_counts.sql` | Contrato de integridad de la migración |

Ningún archivo almacena contraseñas. Los scripts solicitan las contraseñas sin
mostrarlas y las eliminan del entorno al finalizar.

## 5. Fases y criterios de salida

### Fase A — Respaldo de emergencia

1. Usar la cadena **Session pooler** de Supabase, puerto 5432.
2. Ejecutar `export_supabase.sh` con un cliente PostgreSQL 17 o superior.
3. Conservar juntos el dump, `source-counts.csv`, migraciones y manifiesto.
4. Subir el directorio al bucket S3 cifrado y conservar otra copia descargada.

Variables necesarias; la contraseña no se escribe en el historial:

```bash
export SOURCE_DB_HOST='HOST_SESSION_POOLER'
export SOURCE_DB_PORT='5432'
export SOURCE_DB_NAME='postgres'
export SOURCE_DB_USER='postgres.<PROJECT_REF>'
bash scripts/aws/export_supabase.sh
```

**Salida obligatoria:** `pg_restore --list` exitoso y SHA-256 en
`manifest.txt`.

### Fase B — Infraestructura de ensayo

1. Abrir CloudFormation en `us-east-1`.
2. Crear un stack desde `infra/aws/p0-stack.yaml`.
3. Mantener `t3.micro`, `db.t4g.micro` y 20 GiB.
4. Mantener `BackupRetentionPeriod: 0` mientras la cuenta use AWS Free Plan.
   En este tipo de cuenta RDS rechaza cualquier retención automática distinta
   de cero. Los respaldos lógicos PostgreSQL cifrados y versionados en S3,
   junto con una segunda copia local, cubren la recuperación durante la
   migración. Al pasar voluntariamente a Paid Plan se puede habilitar la
   retención automática mediante un cambio revisado por separado.
5. Confirmar la suscripción de alarmas que llegará por email.
6. No modificar Cloudflare.

La plantilla crea dos subredes privadas para RDS sin rutas de Internet. El
puerto 5432 solo acepta tráfico originado en el grupo de seguridad de EC2.

### Fase C — Restauración y verificación

Desde EC2, mediante Systems Manager:

```bash
export TARGET_DB_HOST='ENDPOINT_PRIVADO_RDS'
export TARGET_DB_PORT='5432'
export TARGET_DB_NAME='tradeflow'
export TARGET_DB_USER='tradeflow_admin'
bash scripts/aws/restore_rds.sh backups/supabase-*/tradeflow-public.dump
bash scripts/aws/verify_migration.sh backups/supabase-*/source-counts.csv
```

Después se ejecutan dentro de la imagen Django:

```bash
python manage.py check
python manage.py migrate --check
python manage.py check_database
python manage.py verify_integrations
```

**Go:** conteos idénticos, cero migraciones pendientes y pruebas de login,
catálogo, carrito, checkout, seller y admin aprobadas.  
**No-go:** cualquier diferencia de conteos, error de migración o fallo del
healthcheck.

### Fase D — Media S3, imagen y entorno staging

1. Actualizar primero el stack con `infra/aws/p0-stack.yaml`. La actualización
   crea `MediaBucket`, amplía el rol de la instancia y mantiene IMDSv2
   obligatorio con hop limit 2 para que boto3 funcione dentro de Docker.
2. Copiar los outputs `GitHubDeployRoleArn`, `AppInstanceId` y
   `MediaBucketName` al environment de GitHub `aws-staging`:

- `AWS_ROLE_TO_ASSUME`
- `AWS_EC2_INSTANCE_ID`
- `AWS_MEDIA_BUCKET_NAME`

El environment debe limitarse a ramas protegidas y requerir aprobación manual.
El workflow solo se ejecuta mediante `workflow_dispatch`; nunca se despliega
por cada push. Antes de reemplazar el contenedor, rescata `/app/media` hacia el
volumen del host. Después el helper copia ese volumen de forma aditiva al
bucket (sin `--delete`). Esto conserva la imagen de prueba que reveló el fallo
si todavía existe en el contenedor o volumen actual, además de cualquier otro
archivo local recuperable. Luego actualiza `runtime.env`, reinicia el
contenedor y ejecuta este probe reversible antes de declarar éxito:

```bash
python manage.py check_media_storage --require-remote --write-test
```

El probe crea un objeto bajo `_health/`, verifica lectura y URL, lo elimina y
confirma que no quedó disponible. No imprime parámetros de firma. Si falla,
el script restaura automáticamente el contenedor y el `runtime.env` anteriores.

Actualizar el `UserData` de CloudFormation no vuelve a ejecutar por sí solo el
script de arranque en una instancia EC2 existente. Por eso el helper del
workflow aplica estas variables al contenedor actual sin reemplazar la
instancia.

**Salida obligatoria:** `Remote storage: True` y
`Media create/read/delete test: OK`.

### Fase E — Corte

1. Anunciar mantenimiento y bloquear escrituras.
2. Ejecutar un dump final y repetir la verificación.
3. Desplegar la imagen aprobada en AWS.
4. Probar el origen usando la IP de salida del stack sin cambiar DNS.
5. Cambiar Cloudflare únicamente después del go/no-go.
6. Mantener Railway y Supabase sin cambios durante al menos 72 horas.

Si falla antes de admitir escrituras en AWS, Cloudflare permanece o vuelve a
Railway. Después de admitir escrituras, el rollback exige exportar las nuevas
filas; no se debe apuntar silenciosamente a la base antigua.

## 6. Prohibiciones operativas

- No hacer RDS públicamente accesible.
- No abrir PostgreSQL a `0.0.0.0/0`.
- No pegar contraseñas en GitHub, CloudFormation, chat o comandos visibles.
- No hacer público el bucket de media ni agregar access keys estáticas al `.env`.
- No actualizar AWS al plan Paid.
- No borrar Supabase ni Railway durante la estabilización.
- No fusionar este cambio con trabajo visual del admin.

## 7. Pendientes posteriores al P0

- Instalar un certificado Cloudflare Origin y activar Full (strict).
- Restringir los puertos 80/443 del origen a las redes publicadas por
  Cloudflare.
- Verificar en staging una carga real desde seller: guardar, reabrir el
  producto y abrir la imagen desde catálogo antes del corte.
- Evaluar `t3.small` solo si memoria o latencia lo justifican.
- Corregir por separado las imágenes de producto ausentes; no forman parte del
  dump PostgreSQL.
