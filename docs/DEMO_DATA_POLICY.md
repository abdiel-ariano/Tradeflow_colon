# Política de datos de demostración

## Propósito

TradeFlow Colón todavía no opera con empresas comerciales reales. Mientras el
catálogo contenga identidades, inventario, precios o indicadores generados, la
interfaz debe identificarlos de manera visible como datos simulados.

Esta política evita presentar empresas ficticias como proveedores verificados y
mantiene separada la capacidad técnica de la plataforma de su actividad
comercial real.

## Configuración

La variable de entorno es:

```dotenv
DEMO_CATALOG_DISCLOSURE=true
```

Si no se define, Django la activa cuando `EXPO_DEMO_MODE` o
`SEED_DEMO_IF_EMPTY` están habilitados.

## Comportamiento visible

Con la divulgación activa:

- aparece un aviso persistente en todas las superficies basadas en
  `templates/core/base.html`;
- los proveedores simulados se muestran como **Demo supplier** o
  **Proveedor demo**;
- la tasa de recompra generada se sustituye por un indicador explícitamente
  simulado;
- las imágenes de referencia conservan su etiqueta independiente.

El aviso no es descartable. Ocultarlo mediante cookies dejaría a nuevos
visitantes sin el contexto necesario para interpretar correctamente el
catálogo.

## Retiro del modo de demostración

Antes de configurar `DEMO_CATALOG_DISCLOSURE=false`, el responsable del
despliegue debe confirmar:

1. que cada empresa visible autorizó su publicación;
2. que la verificación CFZ tiene evidencia y fecha registrada;
3. que precios, inventario y cantidades mínimas provienen del proveedor;
4. que las métricas de recompra se calculan con órdenes reales;
5. que los productos generados fueron retirados o separados del catálogo real;
6. que soporte, privacidad y términos describen la operación comercial activa.

## Contrato de implementación

El contexto se expone mediante
`core.context_processors.demo_catalog_context`. El procesador no consulta la
base de datos y es seguro para rutas públicas, portales y administración.

Las modificaciones Python relacionadas deben mantener PEP 8, incluir docstrings
y contar con pruebas de regresión antes de fusionarse.

