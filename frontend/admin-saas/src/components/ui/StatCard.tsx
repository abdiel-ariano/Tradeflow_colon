import { cn } from '@/lib/utils';

export type StatCardProps = {
  label: string;
  value: string;
  subtext?: string;
  trend?: number;
  className?: string;
};

export function StatCard({ label, value, subtext, trend, className }: StatCardProps) {
  return (
    <div className={cn('flex flex-col gap-1 rounded-xl border border-gray-border bg-white p-6 shadow-card', className)}>
      <span className="text-label uppercase tracking-widest text-gray-mid">{label}</span>
      <p className="text-[1.75rem] font-bold leading-tight text-navy">{value}</p>
      {subtext ? <p className="text-sm text-gray-mid">{subtext}</p> : null}
      {trend !== undefined ? (
        <p
          className={cn(
            'text-sm font-semibold',
            trend >= 0 ? 'text-status-paid' : 'text-status-cancelled',
          )}
        >
          {trend >= 0 ? '+' : ''}
          {trend}%
        </p>
      ) : null}
    </div>
  );
}
