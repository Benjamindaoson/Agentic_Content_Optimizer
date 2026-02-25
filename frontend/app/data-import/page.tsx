'use client';

import React from 'react';
import ImportWizard from '@/components/data-import/ImportWizard';
import { Database, ShieldCheck, Download, Info } from 'lucide-react';

export default function DataImportPage() {
    return (
        <div className="min-h-screen bg-background p-8">
            <div className="max-w-5xl mx-auto">
                <header className="mb-12 text-center">
                    <h1 className="text-4xl font-bold text-accent mb-4">数据中心</h1>
                    <p className="text-muted-foreground max-w-2xl mx-auto">
                        当自动化爬虫受限时，可以通过手动导入来维持系统的数据飞轮。
                        支持导入外部优质爆款案例、自有历史笔记以及最新的互动数据。
                    </p>
                </header>

                <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                    {/* Main Wizard */}
                    <div className="lg:col-span-2">
                        <ImportWizard />
                    </div>

                    {/* Sidebar: Info & Templates */}
                    <div className="space-y-6">
                        <div className="bg-primary/5 border border-primary/20 p-6 rounded-2xl">
                            <h4 className="font-bold flex items-center gap-2 mb-3">
                                <Info size={18} className="text-primary" />
                                导入规范
                            </h4>
                            <ul className="text-sm space-y-3 text-muted-foreground">
                                <li className="flex gap-2">
                                    <div className="text-primary">01</div>
                                    内容字段必须包含 note_id，它是系统识别和关联数据的唯一标识。
                                </li>
                                <li className="flex gap-2">
                                    <div className="text-primary">02</div>
                                    CSV 文件请务必保持 UTF-8 编码，否则可能导致文字出现乱码。
                                </li>
                            </ul>
                        </div>

                        <div className="bg-card border border-border p-6 rounded-2xl">
                            <h4 className="font-bold mb-4">下载模板</h4>
                            <div className="space-y-3">
                                <a
                                    href="http://localhost:8080/api/data/import/template?template_type=notes"
                                    target="_blank"
                                    className="w-full flex items-center justify-between p-3 rounded-xl bg-accent/5 hover:bg-accent/10 border border-border transition-all"
                                >
                                    <div className="flex items-center gap-3">
                                        <Database size={20} className="text-blue-400" />
                                        <span className="text-sm font-medium">爆款笔记模板</span>
                                    </div>
                                    <Download size={16} className="text-muted-foreground" />
                                </a>
                                <a
                                    href="http://localhost:8080/api/data/import/template?template_type=feedback"
                                    target="_blank"
                                    className="w-full flex items-center justify-between p-3 rounded-xl bg-accent/5 hover:bg-accent/10 border border-border transition-all"
                                >
                                    <div className="flex items-center gap-3">
                                        <ShieldCheck size={20} className="text-green-400" />
                                        <span className="text-sm font-medium">反馈指标模板</span>
                                    </div>
                                    <Download size={16} className="text-muted-foreground" />
                                </a>
                            </div>
                        </div>

                        <div className="p-6 bg-yellow-500/10 border border-yellow-500/20 rounded-2xl">
                            <p className="text-xs text-yellow-500 leading-relaxed font-medium">
                                ⚠️ 注意：导入大规模数据（超过 10,000 条）可能导致短暂的系统检索延迟，建议分批导入。
                            </p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
