'use client';

import * as React from 'react';
import { cn } from '@/lib/utils';

type ButtonVariant = 'default' | 'outline' | 'ghost';
type ButtonSize = 'default' | 'sm';

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, type = 'button', variant = 'default', size = 'default', ...props }, ref) => {
    const variantClass =
      variant === 'outline'
        ? 'bg-transparent border border-white/20 text-white/90 hover:bg-white/5'
        : variant === 'ghost'
          ? 'bg-transparent text-white/80 hover:bg-white/5'
          : 'bg-primary text-primary-foreground hover:bg-primary/90';

    const sizeClass = size === 'sm' ? 'h-8 px-3 py-1 text-xs' : 'h-10 px-4 py-2 text-sm';
    return (
      <button
        ref={ref}
        type={type}
        className={cn(
          'inline-flex items-center justify-center rounded-lg font-medium',
          sizeClass,
          variantClass,
          'disabled:opacity-50 disabled:cursor-not-allowed',
          className
        )}
        {...props}
      />
    );
  }
);

Button.displayName = 'Button';

