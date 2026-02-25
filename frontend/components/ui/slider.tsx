'use client';

import * as React from 'react';
import { cn } from '@/lib/utils';

interface SliderProps {
  value: number[];
  onValueChange: (value: number[]) => void;
  min?: number;
  max?: number;
  step?: number;
  className?: string;
  disabled?: boolean;
}

export function Slider({
  value,
  onValueChange,
  min = 0,
  max = 100,
  step = 1,
  className,
  disabled,
}: SliderProps) {
  const v = value?.[0] ?? min;
  return (
    <input
      type="range"
      min={min}
      max={max}
      step={step}
      disabled={disabled}
      value={v}
      onChange={(e) => onValueChange([Number(e.target.value)])}
      className={cn('w-full accent-purple-500', className)}
    />
  );
}

