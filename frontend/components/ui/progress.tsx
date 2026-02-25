'use client';

import * as React from 'react';
import { cn } from '@/lib/utils';

export interface ProgressProps extends React.HTMLAttributes<HTMLDivElement> {
  value?: number; // 0-100
}

export function Progress({ value = 0, className, ...props }: ProgressProps) {
  const clamped = Math.max(0, Math.min(100, value));
  return (
    <div
      className={cn('h-2 w-full overflow-hidden rounded-full bg-white/10', className)}
      {...props}
    >
      <div className="h-full bg-purple-500 transition-all" style={{ width: `${clamped}%` }} />
    </div>
  );
}

