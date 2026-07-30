# Analítica IA — límites por plan SaaS

Fuente de verdad en código: `core/utils/analytics_ai_entitlements.py`.  
Campo ORM: `SaasPlan.analytics_ai_tier` (`company` | `market` | `enterprise`).

No hay API de analytics aún: el alcance es solo el dashboard y el chat IA del portal vendedor.  
**No hay tope de filas**: se cargan todas las líneas de venta dentro del historial del plan.

## Mapa plan → tier

| Plan | Slug | Tier | Label UI |
|------|------|------|----------|
| Digitalízate | `digitalizate` | `company` | IA Empresa |
| Expansión | `expansion` | `company`* | IA Empresa |
| Corporativo Pro | `corporativo_pro` | `market` | IA Mercado |
| Ecosistema Enterprise | `ecosistema_enterprise` | `enterprise` | IA Ecosistema |

\* Expansión usa el mismo tier `company` pero con cuotas más altas (override por slug).

## Límites cuantitativos

| Plan | Historial (`history_months`) | Chats IA / día (`chat_per_day`) | Filas |
|------|------------------------------|----------------------------------|-------|
| Digitalízate | 6 | 25 | sin tope |
| Expansión | 12 | 50 | sin tope |
| Corporativo Pro | 18 | 80 | sin tope |
| Ecosistema Enterprise | 36 | 300 | sin tope |

La cuota de chat se cuenta por empresa y día local (`analytics:ai:chat:{company_id}:{YYYY-MM-DD}` en cache).

## Capacidades por alcance

| Capacidad | Digitalízate | Expansión | Corporativo Pro | Ecosistema Enterprise |
|-----------|:------------:|:---------:|:---------------:|:---------------------:|
| Análisis de ventas propias | ✓ | ✓ | ✓ | ✓ |
| Forecast básico | ✓ | ✓ | ✓ | ✓ |
| Benchmarks anónimos ZLC (`allow_market`) | — | — | ✓ | ✓ |
| IA predictiva (`allow_predictive`) | — | — | — | ✓ |
| Cohortes (`allow_cohorts`) | — | — | — | ✓ |
| Escenarios (`allow_scenarios`) | — | — | — | ✓ |

Si el chat pide mercado / competencia / ZLC / benchmarks y el plan no tiene `allow_market`, se responde con hint de upgrade a Corporativo Pro o Enterprise.

## Resolución en runtime

1. `subscription_usage_snapshot(company)` → plan activo.
2. `tier_for_plan(plan)` → lee `analytics_ai_tier` o fallback por slug.
3. `entitlement_for_tier(tier, plan_slug=…)` → aplica override de Expansión.
4. Analytics (`analytics/views.py`, `analytics/data_source.py`) acota solo por historial y aplica cuotas de chat.

## Copy comercial

Los textos públicos y el contexto del asistente Groq viven en `core/utils/saas_plan_catalog.py` (`SAAS_PLANS_AI_ROWS`, `PLAN_MARKETING`). Mantenerlos alineados con esta tabla al cambiar límites.
