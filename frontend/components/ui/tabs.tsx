'use client';

import * as React from 'react';
import { cn } from '@/lib/utils';

type TabsContextValue = {
  value: string;
  setValue: (v: string) => void;
};

const TabsContext = React.createContext<TabsContextValue | null>(null);

export function Tabs({
  value,
  onValueChange,
  defaultValue,
  className,
  children,
}: {
  value?: string;
  onValueChange?: (v: string) => void;
  defaultValue?: string;
  className?: string;
  children: React.ReactNode;
}) {
  const [inner, setInner] = React.useState(defaultValue || '');
  const current = value ?? inner;

  const setValue = React.useCallback(
    (v: string) => {
      if (value === undefined) setInner(v);
      onValueChange?.(v);
    },
    [onValueChange, value]
  );

  return (
    <TabsContext.Provider value={{ value: current, setValue }}>
      <div className={cn('w-full', className)}>{children}</div>
    </TabsContext.Provider>
  );
}

export function TabsList({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('inline-flex h-10 items-center gap-1 rounded-lg bg-white/5 p-1', className)} {...props} />;
}

export function TabsTrigger({
  value,
  className,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { value: string }) {
  const ctx = React.useContext(TabsContext);
  if (!ctx) throw new Error('TabsTrigger must be used within Tabs');
  const active = ctx.value === value;
  return (
    <button
      type="button"
      onClick={() => ctx.setValue(value)}
      className={cn(
        'inline-flex items-center justify-center rounded-md px-3 py-1.5 text-sm',
        active ? 'bg-white/10 text-white' : 'text-white/70 hover:bg-white/5',
        className
      )}
      {...props}
    />
  );
}

export function TabsContent({
  value,
  className,
  children,
  ...props
}: React.HTMLAttributes<HTMLDivElement> & { value: string }) {
  const ctx = React.useContext(TabsContext);
  if (!ctx) throw new Error('TabsContent must be used within Tabs');
  if (ctx.value !== value) return null;
  return (
    <div className={cn('mt-2', className)} {...props}>
      {children}
    </div>
  );
}

