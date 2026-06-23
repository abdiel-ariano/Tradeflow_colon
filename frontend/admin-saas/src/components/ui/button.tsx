import * as React from 'react';
import { Slot } from '@radix-ui/react-slot';
import { cva, type VariantProps } from 'class-variance-authority';
import { Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';

const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 whitespace-nowrap font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-orange/40 disabled:pointer-events-none disabled:opacity-50',
  {
    variants: {
      variant: {
        primary: 'bg-orange text-white hover:bg-[#c93d0c] border-2 border-orange',
        secondary: 'border-2 border-navy text-navy bg-transparent hover:bg-navy hover:text-white',
        ghost: 'text-orange hover:bg-orange-light border-2 border-transparent',
        danger: 'bg-red-500 text-white hover:bg-red-600 border-2 border-red-500',
        destructive: 'bg-red-500 text-white hover:bg-red-600 border-2 border-red-500',
        outline: 'border border-gray-border bg-card hover:bg-muted text-foreground',
      },
      size: {
        sm: 'h-8 px-3 text-sm rounded-lg',
        md: 'h-10 px-5 text-sm rounded-lg',
        lg: 'h-12 px-6 text-base rounded-xl',
      },
    },
    defaultVariants: { variant: 'primary', size: 'md' },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
  loading?: boolean;
  icon?: React.ReactNode;
  iconPosition?: 'left' | 'right';
  fullWidth?: boolean;
}

export function Button({
  className,
  variant,
  size,
  asChild = false,
  loading = false,
  icon,
  iconPosition = 'left',
  fullWidth,
  children,
  disabled,
  ...props
}: ButtonProps) {
  const Comp = asChild ? Slot : 'button';
  return (
    <Comp
      className={cn(buttonVariants({ variant, size, className }), fullWidth && 'w-full')}
      disabled={disabled || loading}
      {...props}
    >
      {loading ? (
        <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
      ) : (
        <>
          {icon && iconPosition === 'left' ? icon : null}
          {children}
          {icon && iconPosition === 'right' ? icon : null}
        </>
      )}
    </Comp>
  );
}
