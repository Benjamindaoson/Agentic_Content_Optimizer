'use client';

import { useState } from 'react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

export function CreateProjectDialog({
  open,
  onClose,
  onSuccess,
}: {
  open: boolean;
  onClose: () => void;
  onSuccess?: () => void;
}) {
  const [name, setName] = useState('');

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50">
      <div className="absolute inset-0 bg-black/70" onClick={onClose} />
      <div className="absolute left-1/2 top-1/2 w-[92vw] max-w-lg -translate-x-1/2 -translate-y-1/2">
        <Card className="bg-[#0c0c12] border-white/10 p-4">
          <div className="text-sm font-medium text-white">创建项目</div>
          <div className="mt-3 space-y-2">
            <div className="text-xs text-white/60">项目名称</div>
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="例如：护肤内容增长实验" />
          </div>
          <div className="mt-4 flex justify-end gap-2">
            <Button variant="ghost" onClick={onClose}>
              取消
            </Button>
            <Button
              onClick={() => {
                onSuccess?.();
                onClose();
              }}
              disabled={!name.trim()}
            >
              创建
            </Button>
          </div>
          <div className="mt-3 text-xs text-white/50">该弹窗为占位实现，用于保证页面可编译。</div>
        </Card>
      </div>
    </div>
  );
}

