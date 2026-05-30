import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import {
  ArrowUpRight,
  Building2,
  DollarSign,
  Sparkles,
  TrendingUp,
  Users,
} from 'lucide-react';
import { toast, Toaster } from 'sonner';
import { KpiCard } from '@/components/KpiCard';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { currencyUsd, formatUsdK } from '@/lib/utils';

export const MONTHS_ES = [
  'Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun',
  'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic',
];

/** Datos de respaldo si la API aún no responde (desarrollo). */
export const historicalSales = [42000, 45500, 49800, 52300, 56100, 61200, 64900, 70400, 74800];

type PlanUsageRow = {
  slug: string;
  name: string;
  count: number;
  limit: number;
  monthly_income_usd: number;
  color: string;
  occupancy_pct: number;
  volume_usd?: number;
};

export const planUsageFallback: PlanUsageRow[] = [
  { slug: 'digitalizate', name: 'Digitalízate', count: 0, limit: 200, monthly_income_usd: 0, color: 'oklch(0.7 0.15 200)', occupancy_pct: 0 },
  { slug: 'expansion', name: 'Expansión', count: 0, limit: 150, monthly_income_usd: 0, color: 'oklch(0.65 0.18 260)', occupancy_pct: 0 },
  { slug: 'corporativo_pro', name: 'Corporativo Pro', count: 0, limit: 50, monthly_income_usd: 0, color: 'oklch(0.6 0.2 30)', occupancy_pct: 0 },
  { slug: 'ecosistema_enterprise', name: 'Ecosistema Enterprise', count: 0, limit: 20, monthly_income_usd: 0, color: 'oklch(0.65 0.18 145)', occupancy_pct: 0 },
];

export type PlanRequest = {
  id: string;
  pk: number;
  company: string;
  from_plan: string;
  to_plan: string;
  reason: string;
  date: string;
  status: 'pending' | 'en_revision' | 'approved' | 'rejected';
};

type ApiPayload = {
  kpis: {
    companies_active: number;
    companies_active_delta: number;
    monthly_revenue_usd: number;
    monthly_revenue_delta_pct: number;
    capacity_used_pct: number;
    capacity_active: number;
    capacity_total: number;
    pending_requests: number;
  };
  plan_usage: PlanUsageRow[];
  requests: PlanRequest[];
  revenue_by_plan: { name: string; value: number; color: string }[];
  sales_trend: { month: string; revenue_usd: number }[];
  predictive: {
    next_month_label: string;
    predicted_amount_usd: number;
    confidence_pct: number;
    monthly_trend_pct: number;
    trend: string;
    trend_label: string;
    chart: { month: string; real: number | null; predicted: number | null; is_today_boundary?: boolean }[];
    predictive_ai_active: boolean;
  };
};

function ChartTooltipCard({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: { value: number; name: string; color?: string }[];
  label?: string;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-border bg-card px-3 py-2 shadow-md text-sm">
      <p className="font-medium text-foreground mb-1">{label}</p>
      {payload.map((p) => (
        <p key={p.name} style={{ color: p.color }} className="text-muted-foreground">
          {p.name}: {currencyUsd.format(Number(p.value))}
        </p>
      ))}
    </div>
  );
}

function getCsrfToken(): string {
  const match = document.cookie.match(/csrftoken=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : '';
}

export function AdminSaasDashboard() {
  const [data, setData] = useState<ApiPayload | null>(null);
  const [requests, setRequests] = useState<PlanRequest[]>([]);
  const [loading, setLoading] = useState(true);

  const apiUrl =
    (document.getElementById('admin-saas-root')?.dataset.apiUrl as string) ||
    '/api/admin/saas-stats/';

  const loadStats = useCallback(async () => {
    try {
      const res = await fetch(apiUrl, { credentials: 'same-origin' });
      if (!res.ok) throw new Error('stats');
      const json = (await res.json()) as ApiPayload;
      setData(json);
      setRequests(
        json.requests.map((r) => ({
          ...r,
          status: r.status === 'en_revision' ? 'pending' : r.status,
        })),
      );
    } catch {
      toast.error('No se pudieron cargar las métricas. Mostrando datos de respaldo.');
      setData(null);
      setRequests([]);
    } finally {
      setLoading(false);
    }
  }, [apiUrl]);

  useEffect(() => {
    loadStats();
  }, [loadStats]);

  const kpis = data?.kpis ?? {
    companies_active: 0,
    companies_active_delta: 0,
    monthly_revenue_usd: 0,
    monthly_revenue_delta_pct: 0,
    capacity_used_pct: 0,
    capacity_active: 0,
    capacity_total: 420,
    pending_requests: 0,
  };

  const planUsage = data?.plan_usage?.length ? data.plan_usage : planUsageFallback;
  const predictive = data?.predictive;
  const salesTrend = data?.sales_trend?.length
    ? data.sales_trend
    : historicalSales.map((v, i) => ({ month: MONTHS_ES[i], revenue_usd: v }));

  const areaChartData = useMemo(() => {
    if (predictive?.chart?.length) {
      return predictive.chart.map((c) => ({
        month: c.month,
        real: c.real ?? undefined,
        predicted: c.predicted ?? undefined,
        boundary: c.is_today_boundary,
      }));
    }
    const hist = historicalSales.map((v, i) => ({
      month: MONTHS_ES[i],
      real: v,
      predicted: undefined as number | undefined,
    }));
    const slope = linearRegressionForecast(historicalSales, 3);
    return [
      ...hist,
      ...slope.map((v, i) => ({
        month: MONTHS_ES[(9 + i) % 12],
        real: undefined as number | undefined,
        predicted: v,
        boundary: i === 0,
      })),
    ];
  }, [predictive]);

  const predictedAmount = predictive?.predicted_amount_usd ?? linearRegressionForecast(historicalSales, 1)[0];
  const nextMonth = predictive?.next_month_label ?? MONTHS_ES[new Date().getMonth() % 12];
  const confidence = predictive?.confidence_pct ?? 78;
  const trendPct = predictive?.monthly_trend_pct ?? 8.4;

  const pendingCount = requests.filter((r) => r.status === 'pending').length;

  const handleRequestAction = async (req: PlanRequest, action: 'approve' | 'reject') => {
    const actionUrl = `/api/admin/saas-requests/${req.pk}/`;
    try {
      const res = await fetch(actionUrl, {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCsrfToken(),
        },
        body: JSON.stringify({ action }),
      });
      const body = await res.json();
      if (!res.ok) throw new Error(body.error || 'Error');
      setRequests((prev) =>
        prev.map((r) =>
          r.id === req.id
            ? { ...r, status: action === 'approve' ? 'approved' : 'rejected' }
            : r,
        ),
      );
      toast.success(body.message || (action === 'approve' ? 'Solicitud aprobada' : 'Solicitud rechazada'));
      loadStats();
    } catch {
      setRequests((prev) =>
        prev.map((r) =>
          r.id === req.id
            ? { ...r, status: action === 'approve' ? 'approved' : 'rejected' }
            : r,
        ),
      );
      toast.success(
        action === 'approve'
          ? `${req.company}: plan activado (modo demo).`
          : `${req.company}: solicitud rechazada (modo demo).`,
      );
    }
  };

  const revenuePie = data?.revenue_by_plan?.length
    ? data.revenue_by_plan
    : planUsage.map((p) => ({
        name: p.name,
        value: p.monthly_income_usd,
        color: p.color,
      }));

  if (loading) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center text-muted-foreground">
        Cargando panel SaaS…
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background px-6 py-8 md:px-10 lg:px-12 max-w-[1400px] mx-auto">
      <Toaster position="top-right" richColors closeButton />

      <header className="sticky top-0 z-20 -mx-6 md:-mx-10 lg:-mx-12 px-6 md:px-10 lg:px-12 py-4 mb-8 flex flex-wrap items-center justify-between gap-4 border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/80">
        <div className="flex items-center gap-4">
          <span className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary text-primary-foreground">
            <Building2 className="h-6 w-6" />
          </span>
          <div>
            <h1 className="text-xl font-bold tracking-tight">Panel de Administración</h1>
            <p className="text-sm text-muted-foreground">Gestión de empresas y planes</p>
          </div>
        </div>
        <Badge variant="default" className="gap-1.5 px-3 py-1">
          <Sparkles className="h-3.5 w-3.5" />
          IA Predictiva activa
        </Badge>
      </header>

      <Card className="mb-8 overflow-hidden">
        <CardHeader className="flex flex-row flex-wrap items-start justify-between gap-4 pb-0">
          <div>
            <Badge variant="secondary" className="mb-2">Análisis Predictivo</Badge>
            <CardTitle className="text-lg font-normal text-muted-foreground">
              Ventas esperadas para{' '}
              <span className="text-foreground font-semibold">{nextMonth}</span> son de{' '}
              <span className="text-primary text-3xl font-bold">
                {currencyUsd.format(predictedAmount)}
              </span>
            </CardTitle>
            <CardDescription className="mt-2">
              Confianza {confidence}% · tendencia mensual{' '}
              {trendPct >= 0 ? '+' : ''}
              {trendPct}% en USD (plataforma)
            </CardDescription>
          </div>
          <div className="flex items-center gap-2 text-emerald font-medium text-sm">
            <TrendingUp className="h-5 w-5" />
            {predictive?.trend_label ?? 'Tendencia positiva'}
          </div>
        </CardHeader>
        <CardContent className="pt-6 h-[280px]">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={areaChartData} margin={{ top: 8, right: 16, left: 8, bottom: 0 }}>
              <defs>
                <linearGradient id="realFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="oklch(0.55 0.15 250)" stopOpacity={0.35} />
                  <stop offset="100%" stopColor="oklch(0.55 0.15 250)" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="predFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="oklch(0.55 0.15 155)" stopOpacity={0.3} />
                  <stop offset="100%" stopColor="oklch(0.55 0.15 155)" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="oklch(0.9 0.01 240)" />
              <XAxis dataKey="month" tick={{ fontSize: 11 }} />
              <YAxis tickFormatter={formatUsdK} tick={{ fontSize: 11 }} />
              <Tooltip content={<ChartTooltipCard />} />
              <ReferenceLine
                x={areaChartData.find((d) => 'boundary' in d && d.boundary)?.month}
                stroke="oklch(0.5 0.05 250)"
                strokeDasharray="4 4"
                label={{ value: 'Hoy', position: 'top', fontSize: 11 }}
              />
              <Area
                type="monotone"
                dataKey="real"
                name="Ventas reales"
                stroke="oklch(0.5 0.14 250)"
                fill="url(#realFill)"
                strokeWidth={2}
                connectNulls={false}
              />
              <Area
                type="monotone"
                dataKey="predicted"
                name="Proyección"
                stroke="oklch(0.55 0.15 155)"
                fill="url(#predFill)"
                strokeWidth={2}
                strokeDasharray="6 4"
                connectNulls={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-5 mb-8">
        <KpiCard
          title="Empresas activas"
          value={String(kpis.companies_active)}
          delta={`+${kpis.companies_active_delta} este mes`}
          icon={Building2}
        />
        <KpiCard
          title="Ingreso mensual"
          value={currencyUsd.format(kpis.monthly_revenue_usd)}
          delta={`+${kpis.monthly_revenue_delta_pct}% vs mes anterior`}
          icon={DollarSign}
        />
        <KpiCard
          title="Capacidad usada"
          value={`${Math.round(kpis.capacity_used_pct)}%`}
          delta={`${kpis.capacity_active}/${kpis.capacity_total}`}
          icon={Users}
        />
        <KpiCard
          title="Solicitudes pendientes"
          value={String(pendingCount || kpis.pending_requests)}
          delta="Requieren revisión"
          icon={ArrowUpRight}
        />
      </div>

      <Tabs defaultValue="planes" className="w-full">
        <TabsList className="flex flex-wrap h-auto gap-1">
          <TabsTrigger value="planes">Uso de planes</TabsTrigger>
          <TabsTrigger value="solicitudes" className="gap-2">
            Solicitudes
            {(pendingCount || kpis.pending_requests) > 0 && (
              <Badge variant="secondary" className="ml-1 h-5 min-w-5 justify-center px-1.5">
                {pendingCount || kpis.pending_requests}
              </Badge>
            )}
          </TabsTrigger>
          <TabsTrigger value="ingresos">Distribución de ingresos</TabsTrigger>
        </TabsList>

        <TabsContent value="planes">
          <div className="grid lg:grid-cols-2 gap-6">
            <Card className="p-4">
              <CardTitle className="text-base mb-4 px-2">Empresas por plan</CardTitle>
              <div className="h-[260px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={planUsage} layout="vertical" margin={{ left: 8, right: 16 }}>
                    <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                    <XAxis type="number" />
                    <YAxis type="category" dataKey="name" width={120} tick={{ fontSize: 11 }} />
                    <Tooltip content={<ChartTooltipCard />} />
                    <Bar dataKey="count" name="Empresas" radius={[0, 6, 6, 0]}>
                      {planUsage.map((p) => (
                        <Cell key={p.slug} fill={p.color} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Card>
            <div className="space-y-4">
              {planUsage.map((plan) => (
                <Card key={plan.slug} className="p-4">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span
                        className="h-2.5 w-2.5 rounded-full"
                        style={{ background: plan.color }}
                      />
                      <span className="font-medium">{plan.name}</span>
                    </div>
                    <span className="text-sm text-muted-foreground">
                      {plan.count}/{plan.limit}
                    </span>
                  </div>
                  <Progress value={plan.occupancy_pct} className="h-2 mb-2" />
                  <p className="text-sm text-muted-foreground">
                    Ingreso mensual:{' '}
                    <strong className="text-foreground">
                      {currencyUsd.format(plan.monthly_income_usd)}
                    </strong>
                    {plan.volume_usd != null && plan.volume_usd > 0 && (
                      <span className="ml-2">
                        · GMV período: {currencyUsd.format(plan.volume_usd)}
                      </span>
                    )}
                  </p>
                </Card>
              ))}
            </div>
          </div>
        </TabsContent>

        <TabsContent value="solicitudes">
          <Card>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>ID</TableHead>
                  <TableHead>Empresa</TableHead>
                  <TableHead>Actual → Solicitado</TableHead>
                  <TableHead>Motivo</TableHead>
                  <TableHead>Fecha</TableHead>
                  <TableHead>Estado</TableHead>
                  <TableHead>Acciones</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {requests.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={7} className="text-center text-muted-foreground py-8">
                      No hay solicitudes pendientes
                    </TableCell>
                  </TableRow>
                ) : (
                  requests.map((req) => (
                    <TableRow key={req.id}>
                      <TableCell className="font-mono text-xs">{req.id}</TableCell>
                      <TableCell className="font-medium">{req.company}</TableCell>
                      <TableCell>
                        <div className="flex items-center gap-1 flex-wrap">
                          <Badge variant="secondary">{req.from_plan}</Badge>
                          <ArrowUpRight className="h-3 w-3 text-muted-foreground shrink-0" />
                          <Badge variant="default">{req.to_plan}</Badge>
                        </div>
                      </TableCell>
                      <TableCell className="max-w-[200px] truncate text-muted-foreground">
                        {req.reason}
                      </TableCell>
                      <TableCell className="text-sm whitespace-nowrap">
                        {new Date(req.date).toLocaleDateString('es-PA')}
                      </TableCell>
                      <TableCell>
                        {req.status === 'pending' && (
                          <Badge variant="secondary">Pendiente</Badge>
                        )}
                        {req.status === 'approved' && (
                          <Badge variant="emerald">Aprobado</Badge>
                        )}
                        {req.status === 'rejected' && (
                          <Badge variant="destructive">Rechazado</Badge>
                        )}
                      </TableCell>
                      <TableCell>
                        {req.status === 'pending' && (
                          <div className="flex gap-2">
                            <Button size="sm" onClick={() => handleRequestAction(req, 'approve')}>
                              Aprobar
                            </Button>
                            <Button
                              size="sm"
                              variant="destructive"
                              onClick={() => handleRequestAction(req, 'reject')}
                            >
                              Rechazar
                            </Button>
                          </div>
                        )}
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </Card>
        </TabsContent>

        <TabsContent value="ingresos">
          <div className="grid lg:grid-cols-2 gap-6">
            <Card className="p-4">
              <CardTitle className="text-base mb-4 px-2">Participación por plan</CardTitle>
              <div className="h-[280px]">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={revenuePie}
                      dataKey="value"
                      nameKey="name"
                      innerRadius={60}
                      outerRadius={100}
                      paddingAngle={2}
                    >
                      {revenuePie.map((entry) => (
                        <Cell key={entry.name} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip content={<ChartTooltipCard />} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </Card>
            <Card className="p-4">
              <CardTitle className="text-base mb-4 px-2">Tendencia de ventas (9 meses)</CardTitle>
              <div className="h-[280px]">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={salesTrend}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="month" tick={{ fontSize: 11 }} />
                    <YAxis tickFormatter={formatUsdK} tick={{ fontSize: 11 }} />
                    <Tooltip content={<ChartTooltipCard />} />
                    <Line
                      type="monotone"
                      dataKey="revenue_usd"
                      name="Ventas"
                      stroke="oklch(0.5 0.14 250)"
                      strokeWidth={2}
                      dot={{ r: 3 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </Card>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}

function linearRegressionForecast(values: number[], count: number): number[] {
  const n = values.length;
  if (n === 0) return Array(count).fill(0);
  const xs = values.map((_, i) => i);
  const sumX = xs.reduce((a, b) => a + b, 0);
  const sumY = values.reduce((a, b) => a + b, 0);
  const sumXY = xs.reduce((acc, x, i) => acc + x * values[i], 0);
  const sumX2 = xs.reduce((acc, x) => acc + x * x, 0);
  const denom = n * sumX2 - sumX * sumX;
  const slope = denom === 0 ? 0 : (n * sumXY - sumX * sumY) / denom;
  const intercept = (sumY - slope * sumX) / n;
  return Array.from({ length: count }, (_, i) =>
    Math.max(0, intercept + slope * (n + i)),
  );
}

/** Export para TanStack Router */
export const Route = AdminSaasDashboard;
