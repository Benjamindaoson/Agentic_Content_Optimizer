'use client';

import * as React from 'react';
import { cn } from '@/lib/utils';

type Option = { value: string; label: string };

interface SelectProps {
  value: string;
  onChange: (value: string) => void;
  options: Option[];
  className?: string;
  disabled?: boolean;
}

export function Select({ value, onChange, options, className, disabled }: SelectProps) {
  return (
    <select
      value={value}
      disabled={disabled}
      onChange={(e) => onChange(e.target.value)}
      className={cn(
        'h-10 w-full rounded-lg border border-white/10 bg-white/5 px-3 text-sm text-white',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/20',
        disabled ? 'opacity-50 cursor-not-allowed' : '',
        className
      )}
    >
      {options.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  );
}

