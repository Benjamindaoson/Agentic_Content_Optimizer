'use client';

import * as React from 'react';
import { cn } from '@/lib/utils';

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  icon?: React.ReactNode;
}

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, type = 'text', icon, ...props }, ref) => {
    return (
      <div className={cn('relative', className)}>
        {icon ? (
          <div className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-white/40">
            {icon}
          </div>
        ) : null}
        <input
          ref={ref}
          type={type}
          className={cn(
            'flex h-10 w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-white',
            icon ? 'pl-9' : '',
            'placeholder:text-white/40',
            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/20',
            'disabled:cursor-not-allowed disabled:opacity-50'
          )}
          {...props}
        />
      </div>
    );
  }
);

Input.displayName = 'Input';

