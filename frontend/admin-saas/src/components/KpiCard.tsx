import type { LucideIcon } from 'lucide-react';
import { Card } from '@/components/ui/card';
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
    <Card className={cn('p-5', className)} hoverable>
      <div className="flex flex-col gap-3 p-0">
        <div className="flex items-start justify-between">
          <span className="text-label uppercase tracking-widest text-gray-mid">{title}</span>
          <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-orange-light text-orange">
            <Icon className="h-4 w-4" />
          </span>
        </div>
        <p className="text-2xl font-bold tracking-tight text-navy">{value}</p>
        <p className="text-xs text-gray-mid">{delta}</p>
      </div>
    </Card>
  );
}
