import * as React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils';

const statusBadgeVariants = cva(
  'inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold capitalize',
  {
    variants: {
      status: {
        paid: 'bg-status-paidbg text-status-paid',
        cancelled: 'bg-status-cancelledbg text-status-cancelled',
        pending: 'bg-status-pendingbg text-status-pending',
        processing: 'bg-blue-50 text-blue-600',
      },
    },
    defaultVariants: { status: 'pending' },
  },
);

export type StatusKind = 'paid' | 'cancelled' | 'pending' | 'processing';

export interface StatusBadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof statusBadgeVariants> {
  status: StatusKind;
  label?: string;
}

export function StatusBadge({ className, status, label, ...props }: StatusBadgeProps) {
  return (
    <span className={cn(statusBadgeVariants({ status }), className)} {...props}>
      {label ?? status}
    </span>
  );
}
