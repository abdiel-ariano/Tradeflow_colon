import type { LucideIcon } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { cn } from '@/lib/utils';

type KpiCardProps = {
  title: string;
  value: string;
  delta: string;
  icon: LucideIcon;
  className?: string;
};

export function KpiCard({ title, value, delta, icon: Icon, className }: KpiCardProps) {
  return (
    <Card className={cn('p-5', className)}>
      <CardContent className="p-0 flex flex-col gap-3">
        <div className="flex items-start justify-between">
          <span className="text-sm text-muted-foreground">{title}</span>
          <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <Icon className="h-4 w-4" />
          </span>
        </div>
        <p className="text-2xl font-bold tracking-tight">{value}</p>
        <p className="text-xs text-muted-foreground">{delta}</p>
      </CardContent>
    </Card>
  );
}
