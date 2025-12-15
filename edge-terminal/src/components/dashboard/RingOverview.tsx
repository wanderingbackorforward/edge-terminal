import React from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '../ui/Card';
import { formatNumber } from '../../lib/utils';
import { Activity, Gauge, Ruler, Zap } from 'lucide-react';
import type { RingSummary } from '../../types/api';

interface RingOverviewProps {
    data: RingSummary | null;
    isLoading?: boolean;
}

export const RingOverview: React.FC<RingOverviewProps> = ({ data, isLoading }) => {
    if (isLoading || !data) {
        return <Card className="h-48 animate-pulse bg-surface/50" ><div /></Card>;
    }

    const items = [
        { label: '推力均值', value: data.mean_thrust, unit: 'kN', icon: Activity },
        { label: '扭矩均值', value: data.mean_torque, unit: 'kNm', icon: Zap },
        { label: '推进速度', value: data.mean_advance_rate, unit: 'mm/min', icon: Gauge },
        { label: '地表沉降', value: data.settlement_value, unit: 'mm', icon: Ruler },
    ];

    return (
        <Card>
            <CardHeader>
                <CardTitle>第{data.ring_number}环 概览</CardTitle>
            </CardHeader>
            <CardContent>
                <div className="grid grid-cols-2 gap-4">
                    {items.map((item, idx) => (
                        <div key={idx} className="flex flex-col p-3 rounded-lg bg-background/50 border border-border/50">
                            <div className="flex items-center gap-2 mb-2 text-text-secondary">
                                <item.icon className="w-4 h-4" />
                                <span className="text-xs font-medium uppercase tracking-wider">{item.label}</span>
                            </div>
                            <div className="flex items-baseline gap-1">
                                <span className="text-xl font-bold font-mono text-text-primary">
                                    {formatNumber(item.value, 1)}
                                </span>
                                <span className="text-xs text-text-muted">{item.unit}</span>
                            </div>
                        </div>
                    ))}
                </div>
            </CardContent>
        </Card>
    );
};
