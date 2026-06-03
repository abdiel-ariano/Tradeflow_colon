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
import { currencyUsd, formatUsdK, monthLabelEn } from '@/lib/utils';

export const MONTHS_EN = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
];

/** TradeFlow Colón brand palette */
const TF_NAVY = '#0F2A44';
const TF_ORANGE = '#F26522';
const TF_BLUE = '#2E5B8A';
const TF_MUTED = '#6B7A88';
const TF_BORDER = '#D1D5DB';

const PLAN_BRAND_COLORS: Record<string, string> = {
  digitalizate: TF_BLUE,
  expansion: TF_ORANGE,
  corporativo_pro: TF_NAVY,
  ecosistema_enterprise: TF_MUTED,
};

function translateTrendLabel(label: string | undefined): string {
  if (!label) return 'Positive trend';
  const map: Record<string, string> = {
    'Tendencia positiva': 'Positive trend',
    'Tendencia negativa': 'Negative trend',
    'Tendencia estable': 'Stable trend',
    'Tendencia a vigilar': 'Trend to watch',
  };
  return map[label] ?? label;
}

function brandColorForPlan(slug: string, fallback: string): string {
  return PLAN_BRAND_COLORS[slug] ?? fallback;
}

/** Fallback data when the API is unavailable (development). */
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
  { slug: 'digitalizate', name: 'Digitalize', count: 0, limit: 200, monthly_income_usd: 0, color: TF_BLUE, occupancy_pct: 0 },
  { slug: 'expansion', name: 'Expansion', count: 0, limit: 150, monthly_income_usd: 0, color: TF_ORANGE, occupancy_pct: 0 },
  { slug: 'corporativo_pro', name: 'Corporate Pro', count: 0, limit: 50, monthly_income_usd: 0, color: TF_NAVY, occupancy_pct: 0 },
  { slug: 'ecosistema_enterprise', name: 'Enterprise', count: 0, limit: 20, monthly_income_usd: 0, color: TF_MUTED, occupancy_pct: 0 },
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
      toast.error('Could not load metrics. Showing fallback data.');
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

  const planUsage = useMemo(() => {
    const rows = data?.plan_usage?.length ? data.plan_usage : planUsageFallback;
    return rows.map((p) => ({
      ...p,
      color: brandColorForPlan(p.slug, p.color),
    }));
  }, [data]);
  const predictive = data?.predictive;
  const salesTrend = data?.sales_trend?.length
    ? data.sales_trend.map((r) => ({
        ...r,
        month: monthLabelEn(r.month),
      }))
    : historicalSales.map((v, i) => ({ month: MONTHS_EN[i], revenue_usd: v }));

  const areaChartData = useMemo(() => {
    if (predictive?.chart?.length) {
      return predictive.chart.map((c) => ({
        month: monthLabelEn(c.month),
        real: c.real ?? undefined,
        predicted: c.predicted ?? undefined,
        boundary: c.is_today_boundary,
      }));
    }
    const hist = historicalSales.map((v, i) => ({
      month: MONTHS_EN[i],
      real: v,
      predicted: undefined as number | undefined,
    }));
    const slope = linearRegressionForecast(historicalSales, 3);
    return [
      ...hist,
      ...slope.map((v, i) => ({
        month: MONTHS_EN[(9 + i) % 12],
        real: undefined as number | undefined,
        predicted: v,
        boundary: i === 0,
      })),
    ];
  }, [predictive]);

  const predictedAmount = predictive?.predicted_amount_usd ?? linearRegressionForecast(historicalSales, 1)[0];
  const nextMonth = monthLabelEn(
    predictive?.next_month_label ?? MONTHS_EN[new Date().getMonth() % 12],
  );
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
      toast.success(body.message || (action === 'approve' ? 'Request approved' : 'Request rejected'));
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
          ? `${req.company}: plan activated (demo mode).`
          : `${req.company}: request rejected (demo mode).`,
      );
    }
  };

  const revenuePie = useMemo(() => {
    const source = data?.revenue_by_plan?.length
      ? data.revenue_by_plan
      : planUsage.map((p) => ({
          name: p.name,
          value: p.monthly_income_usd,
          color: p.color,
        }));
    return source.map((entry) => {
      const plan = planUsage.find((p) => p.name === entry.name);
      return {
        name: entry.name,
        value: entry.value,
        color: plan?.color ?? entry.color,
      };
    });
  }, [data, planUsage]);

  if (loading) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center text-muted-foreground">
        Loading SaaS dashboard…
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background px-6 py-8 md:px-10 lg:px-12 max-w-[1400px] mx-auto">
      <Toaster position="top-right" richColors closeButton />

      <header className="sticky top-0 z-20 -mx-6 md:-mx-10 lg:-mx-12 px-6 md:px-10 lg:px-12 py-4 mb-8 flex flex-wrap items-center justify-between gap-4 border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/80">
        <div className="flex items-center gap-4">
          <span
            className="flex h-12 w-12 items-center justify-center rounded-xl text-primary-foreground"
            style={{ background: TF_NAVY }}
          >
            <Building2 className="h-6 w-6" />
          </span>
          <div>
            <h1 className="text-xl font-bold tracking-tight">Administration Panel</h1>
            <p className="text-sm text-muted-foreground">Company and plan management</p>
          </div>
        </div>
        <Badge variant="default" className="gap-1.5 px-3 py-1">
          <Sparkles className="h-3.5 w-3.5" />
          Predictive AI active
        </Badge>
      </header>

      <Card className="mb-8 overflow-hidden">
        <CardHeader className="flex flex-row flex-wrap items-start justify-between gap-4 pb-0">
          <div>
            <Badge variant="secondary" className="mb-2">Predictive analysis</Badge>
            <CardTitle className="text-lg font-normal text-muted-foreground">
              Expected sales for{' '}
              <span className="text-foreground font-semibold">{nextMonth}</span> are{' '}
              <span className="text-primary text-3xl font-bold">
                {currencyUsd.format(predictedAmount)}
              </span>
            </CardTitle>
            <CardDescription className="mt-2">
              Confidence {confidence}% · monthly trend{' '}
              {trendPct >= 0 ? '+' : ''}
              {trendPct}% in USD (platform)
            </CardDescription>
          </div>
          <div className="flex items-center gap-2 text-emerald font-medium text-sm">
            <TrendingUp className="h-5 w-5" />
            {translateTrendLabel(predictive?.trend_label)}
          </div>
        </CardHeader>
        <CardContent className="pt-6 h-[280px]">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={areaChartData} margin={{ top: 8, right: 16, left: 8, bottom: 0 }}>
              <defs>
                <linearGradient id="realFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={TF_BLUE} stopOpacity={0.35} />
                  <stop offset="100%" stopColor={TF_BLUE} stopOpacity={0} />
                </linearGradient>
                <linearGradient id="predFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={TF_ORANGE} stopOpacity={0.3} />
                  <stop offset="100%" stopColor={TF_ORANGE} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke={TF_BORDER} />
              <XAxis dataKey="month" tick={{ fontSize: 11 }} />
              <YAxis tickFormatter={formatUsdK} tick={{ fontSize: 11 }} />
              <Tooltip content={<ChartTooltipCard />} />
              <ReferenceLine
                x={areaChartData.find((d) => 'boundary' in d && d.boundary)?.month}
                stroke={TF_MUTED}
                strokeDasharray="4 4"
                label={{ value: 'Today', position: 'top', fontSize: 11 }}
              />
              <Area
                type="monotone"
                dataKey="real"
                name="Actual sales"
                stroke={TF_BLUE}
                fill="url(#realFill)"
                strokeWidth={2}
                connectNulls={false}
              />
              <Area
                type="monotone"
                dataKey="predicted"
                name="Forecast"
                stroke={TF_ORANGE}
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
          title="Active companies"
          value={String(kpis.companies_active)}
          delta={`+${kpis.companies_active_delta} this month`}
          icon={Building2}
        />
        <KpiCard
          title="Monthly revenue"
          value={currencyUsd.format(kpis.monthly_revenue_usd)}
          delta={`+${kpis.monthly_revenue_delta_pct}% vs previous month`}
          icon={DollarSign}
        />
        <KpiCard
          title="Capacity used"
          value={`${Math.round(kpis.capacity_used_pct)}%`}
          delta={`${kpis.capacity_active}/${kpis.capacity_total}`}
          icon={Users}
        />
        <KpiCard
          title="Pending requests"
          value={String(pendingCount || kpis.pending_requests)}
          delta="Requires review"
          icon={ArrowUpRight}
        />
      </div>

      <Tabs defaultValue="planes" className="w-full">
        <TabsList className="flex flex-wrap h-auto gap-1">
          <TabsTrigger value="planes">Plan usage</TabsTrigger>
          <TabsTrigger value="solicitudes" className="gap-2">
            Requests
            {(pendingCount || kpis.pending_requests) > 0 && (
              <Badge variant="secondary" className="ml-1 h-5 min-w-5 justify-center px-1.5">
                {pendingCount || kpis.pending_requests}
              </Badge>
            )}
          </TabsTrigger>
          <TabsTrigger value="ingresos">Revenue distribution</TabsTrigger>
        </TabsList>

        <TabsContent value="planes">
          <div className="grid lg:grid-cols-2 gap-6">
            <Card className="p-4">
              <CardTitle className="text-base mb-4 px-2">Companies by plan</CardTitle>
              <div className="h-[260px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={planUsage} layout="vertical" margin={{ left: 8, right: 16 }}>
                    <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                    <XAxis type="number" />
                    <YAxis type="category" dataKey="name" width={120} tick={{ fontSize: 11 }} />
                    <Tooltip content={<ChartTooltipCard />} />
                    <Bar dataKey="count" name="Companies" radius={[0, 6, 6, 0]}>
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
                    Monthly revenue:{' '}
                    <strong className="text-foreground">
                      {currencyUsd.format(plan.monthly_income_usd)}
                    </strong>
                    {plan.volume_usd != null && plan.volume_usd > 0 && (
                      <span className="ml-2">
                        · Period GMV: {currencyUsd.format(plan.volume_usd)}
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
                  <TableHead>Company</TableHead>
                  <TableHead>Current → Requested</TableHead>
                  <TableHead>Reason</TableHead>
                  <TableHead>Date</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {requests.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={7} className="text-center text-muted-foreground py-8">
                      No pending requests
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
                        {new Date(req.date).toLocaleDateString('en-US')}
                      </TableCell>
                      <TableCell>
                        {req.status === 'pending' && (
                          <Badge variant="secondary">Pending</Badge>
                        )}
                        {req.status === 'approved' && (
                          <Badge variant="emerald">Approved</Badge>
                        )}
                        {req.status === 'rejected' && (
                          <Badge variant="destructive">Rejected</Badge>
                        )}
                      </TableCell>
                      <TableCell>
                        {req.status === 'pending' && (
                          <div className="flex gap-2">
                            <Button size="sm" onClick={() => handleRequestAction(req, 'approve')}>
                              Approve
                            </Button>
                            <Button
                              size="sm"
                              variant="destructive"
                              onClick={() => handleRequestAction(req, 'reject')}
                            >
                              Reject
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
              <CardTitle className="text-base mb-4 px-2">Share by plan</CardTitle>
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
              <CardTitle className="text-base mb-4 px-2">Sales trend (9 months)</CardTitle>
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
                      name="Sales"
                      stroke={TF_BLUE}
                      strokeWidth={2}
                      dot={{ r: 3, fill: TF_ORANGE }}
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

/** Export for TanStack Router */
export const Route = AdminSaasDashboard;
