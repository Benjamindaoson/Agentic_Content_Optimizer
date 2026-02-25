'use client';

import React, { useState } from 'react';
import { Upload, FileJson, FileText, CheckCircle2, AlertCircle, Loader2 } from 'lucide-react';
import axios from 'axios';

const ImportWizard: React.FC = () => {
    const [step, setStep] = useState(1);
    const [file, setFile] = useState<File | null>(null);
    const [type, setType] = useState<'notes' | 'feedback'>('notes');
    const [loading, setLoading] = useState(false);
    const [result, setResult] = useState<any>(null);

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files[0]) {
            setFile(e.target.files[0]);
        }
    };

    const handleUpload = async () => {
        if (!file) return;
        setLoading(true);

        try {
            const formData = new FormData();
            formData.append('file', file);

            const endpoint = type === 'notes' ? '/api/data/import/notes/csv' : '/api/data/import/feedback/csv';
            const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080';

            const response = await axios.post(`${apiBase}${endpoint}`, formData, {
                headers: { 'Content-Type': 'multipart/form-data' }
            });

            setResult(response.data);
            setStep(3);
        } catch (err: any) {
            console.error(err);
            setResult({ error: err.response?.data?.detail || '上传失败' });
            setStep(3);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="max-w-2xl mx-auto bg-card border border-border rounded-2xl overflow-hidden shadow-2xl">
            <div className="p-8 border-b border-border bg-accent/5">
                <h2 className="text-2xl font-bold mb-2">数据导入向导</h2>
                <p className="text-muted-foreground text-sm">手动补充爆款数据或线上反馈，增强 RL 训练效果</p>
            </div>

            <div className="p-8">
                {/* Step Indicator */}
                <div className="flex justify-between mb-12 relative">
                    <div className="absolute top-1/2 left-0 w-full h-0.5 bg-border -translate-y-1/2 -z-10" />
                    {[1, 2, 3].map((s) => (
                        <div
                            key={s}
                            className={`w-10 h-10 rounded-full flex items-center justify-center border-2 transition-all ${s <= step ? 'bg-primary border-primary text-white' : 'bg-card border-border text-muted-foreground'
                                }`}
                        >
                            {s < step ? <CheckCircle2 size={20} /> : s}
                        </div>
                    ))}
                </div>

                {/* Step 1: Config */}
                {step === 1 && (
                    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4">
                        <div>
                            <label className="block text-sm font-medium mb-3">1. 选择导入类型</label>
                            <div className="grid grid-cols-2 gap-4">
                                <button
                                    onClick={() => setType('notes')}
                                    className={`p-4 rounded-xl border-2 transition-all text-left flex flex-col gap-2 ${type === 'notes' ? 'border-primary bg-primary/5' : 'border-border hover:border-accent'
                                        }`}
                                >
                                    <FileText className={type === 'notes' ? 'text-primary' : ''} />
                                    <div>
                                        <div className="font-semibold">爆款笔记</div>
                                        <div className="text-xs text-muted-foreground">导入标题、正文和初始权重</div>
                                    </div>
                                </button>
                                <button
                                    onClick={() => setType('feedback')}
                                    className={`p-4 rounded-xl border-2 transition-all text-left flex flex-col gap-2 ${type === 'feedback' ? 'border-primary bg-primary/5' : 'border-border hover:border-accent'
                                        }`}
                                >
                                    <FileJson className={type === 'feedback' ? 'text-primary' : ''} />
                                    <div>
                                        <div className="font-semibold">真实反馈</div>
                                        <div className="text-xs text-muted-foreground">更新已有笔记的阅读、点赞数据</div>
                                    </div>
                                </button>
                            </div>
                        </div>
                        <button
                            className="w-full bg-primary hover:bg-primary/90 text-white font-bold py-3 rounded-xl transition-all"
                            onClick={() => setStep(2)}
                        >
                            下一步
                        </button>
                    </div>
                )}

                {/* Step 2: Upload */}
                {step === 2 && (
                    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4">
                        <div className="border-2 border-dashed border-border rounded-2xl p-12 text-center hover:border-primary/50 transition-all cursor-pointer relative">
                            <input
                                type="file"
                                accept=".csv"
                                className="absolute inset-0 opacity-0 cursor-pointer"
                                onChange={handleFileChange}
                            />
                            <Upload className="mx-auto mb-4 text-muted-foreground" size={48} />
                            <p className="font-medium">{file ? file.name : '点击或拖拽 CSV 文件上传'}</p>
                            <p className="text-xs text-muted-foreground mt-2">支持 UTF-8 编码的 .csv 格式 (最大 20MB)</p>
                        </div>

                        <div className="flex gap-4">
                            <button
                                className="flex-1 bg-accent text-accent-foreground py-3 rounded-xl font-medium"
                                onClick={() => setStep(1)}
                            >
                                上一步
                            </button>
                            <button
                                disabled={!file || loading}
                                className="flex-[2] bg-primary hover:bg-primary/90 text-white py-3 rounded-xl font-bold disabled:opacity-50 flex items-center justify-center gap-2"
                                onClick={handleUpload}
                            >
                                {loading && <Loader2 className="animate-spin" size={20} />}
                                开始上传
                            </button>
                        </div>
                    </div>
                )}

                {/* Step 3: Result */}
                {step === 3 && (
                    <div className="text-center space-y-6 animate-in zoom-in-95">
                        {result?.error ? (
                            <>
                                <AlertCircle size={64} className="mx-auto text-red-500" />
                                <h3 className="text-xl font-bold">导入出错</h3>
                                <p className="text-sm text-red-400 bg-red-500/10 p-4 rounded-lg">{result.error}</p>
                            </>
                        ) : (
                            <>
                                <CheckCircle2 size={64} className="mx-auto text-green-500" />
                                <h3 className="text-xl font-bold">导入任务已提交</h3>
                                <div className="bg-accent/5 p-6 rounded-2xl border border-border grid grid-cols-2 gap-4">
                                    <div>
                                        <div className="text-xs text-muted-foreground">处理总数</div>
                                        <div className="text-2xl font-bold">{result?.summary?.total || 0}</div>
                                    </div>
                                    <div>
                                        <div className="text-xs text-muted-foreground">成功导入</div>
                                        <div className="text-2xl font-bold text-green-400">{result?.summary?.success || 0}</div>
                                    </div>
                                    <div>
                                        <div className="text-xs text-muted-foreground">已跳过 (重复)</div>
                                        <div className="text-2xl font-bold text-yellow-500">{result?.summary?.skipped || 0}</div>
                                    </div>
                                    <div>
                                        <div className="text-xs text-muted-foreground">失败单目</div>
                                        <div className="text-2xl font-bold text-red-500">{result?.summary?.failed || 0}</div>
                                    </div>
                                </div>
                                {result?.errors?.length > 0 && (
                                    <div className="text-left mt-4 text-xs max-h-40 overflow-y-auto bg-black/20 p-4 rounded-lg">
                                        <p className="font-bold mb-2 text-red-400">错误详情:</p>
                                        {result.errors.map((e: any, i: number) => (
                                            <p key={i}>Row {e.row}: {e.field} - {e.message}</p>
                                        ))}
                                    </div>
                                )}
                            </>
                        )}
                        <button
                            className="w-full bg-primary text-white py-3 rounded-xl font-bold"
                            onClick={() => { setStep(1); setFile(null); setResult(null); }}
                        >
                            完成并退出
                        </button>
                    </div>
                )}
            </div>
        </div>
    );
};

export default ImportWizard;
