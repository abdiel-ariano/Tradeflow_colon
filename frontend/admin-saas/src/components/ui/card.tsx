import * as React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils';

const cardVariants = cva('rounded-xl border bg-card text-card-foreground', {
  variants: {
    variant: {
      default: 'border-gray-border shadow-card p-6',
      flat: 'border-gray-border p-6 shadow-none',
      highlighted: 'border-orange shadow-card p-6 ring-1 ring-orange-light',
    },
  },
  defaultVariants: { variant: 'default' },
});

export interface CardProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof cardVariants> {
  hoverable?: boolean;
}

export function Card({ className, variant, hoverable, ...props }: CardProps) {
  return (
    <div
      className={cn(
        cardVariants({ variant }),
        hoverable && 'transition-shadow hover:shadow-card-hover',
        className,
      )}
      {...props}
    />
  );
}

export function CardHeader({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('flex flex-col gap-1.5 pb-2', className)} {...props} />;
}

export function CardTitle({ className, ...props }: React.HTMLAttributes<HTMLHeadingElement>) {
  return <h3 className={cn('text-h3 font-semibold leading-none text-navy', className)} {...props} />;
}

export function CardDescription({ className, ...props }: React.HTMLAttributes<HTMLParagraphElement>) {
  return <p className={cn('text-sm text-muted-foreground', className)} {...props} />;
}

export function CardContent({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('pt-2', className)} {...props} />;
}
