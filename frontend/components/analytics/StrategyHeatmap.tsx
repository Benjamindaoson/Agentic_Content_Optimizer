'use client';

import React from 'react';
import {
    ResponsiveContainer,
    XAxis,
    YAxis,
    Tooltip,
    Cell,
    ScatterChart,
    Scatter,
    ZAxis
} from 'recharts';

interface StrategyData {
    hook: string;
    body: string;
    success_rate: number;
    pulls: number;
}

interface StrategyHeatmapProps {
    data: StrategyData[];
}

const StrategyHeatmap: React.FC<StrategyHeatmapProps> = ({ data }) => {
    // 提取唯一的 hooks 和 bodies 作为坐标轴
    const hooks = Array.from(new Set(data.map(d => d.hook)));
    const bodies = Array.from(new Set(data.map(d => d.body)));

    // 将字符串映射为数字索引
    const chartData = data.map(d => ({
        x: hooks.indexOf(d.hook),
        y: bodies.indexOf(d.body),
        z: d.pulls,
        success_rate: d.success_rate,
        hookName: d.hook,
        bodyName: d.body
    }));

    const CustomTooltip = ({ active, payload }: any) => {
        if (active && payload && payload.length) {
            const d = payload[0].payload;
            return (
                <div className="bg-card border border-border p-3 rounded-lg shadow-xl">
                    <p className="font-bold text-accent">{d.hookName}</p>
                    <p className="text-sm text-muted-foreground">搭配: {d.bodyName}</p>
                    <hr className="my-2 border-border" />
                    <p className="text-sm">成功率: <span className="text-green-400">{(d.success_rate * 100).toFixed(1)}%</span></p>
                    <p className="text-sm">尝试次数: {d.z}</p>
                </div>
            );
        }
        return null;
    };

    return (
        <div className="w-full h-[400px] bg-card/30 p-4 rounded-xl border border-border">
            <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                🔥 策略表现热力图
                <span className="text-xs font-normal text-muted-foreground">(Hook x Body)</span>
            </h3>
            <ResponsiveContainer width="100%" height="90%">
                <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
                    <XAxis
                        type="number"
                        dataKey="x"
                        name="Hook"
                        domain={[0, hooks.length - 1]}
                        tickFormatter={(val) => hooks[val] || ''}
                        stroke="#888"
                        fontSize={10}
                    />
                    <YAxis
                        type="number"
                        dataKey="y"
                        name="Body"
                        domain={[0, bodies.length - 1]}
                        tickFormatter={(val) => bodies[val] || ''}
                        stroke="#888"
                        fontSize={10}
                    />
                    <ZAxis type="number" dataKey="z" range={[50, 400]} name="Pulls" />
                    <Tooltip content={<CustomTooltip />} />
                    <Scatter name="Strategies" data={chartData}>
                        {chartData.map((entry, index) => (
                            <Cell
                                key={`cell-${index}`}
                                fill={entry.success_rate > 0.1 ? '#10b981' : '#3b82f6'}
                                fillOpacity={0.4 + entry.success_rate * 0.6}
                            />
                        ))}
                    </Scatter>
                </ScatterChart>
            </ResponsiveContainer>
        </div>
    );
};

export default StrategyHeatmap;
