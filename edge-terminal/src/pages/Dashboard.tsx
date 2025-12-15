import React, { useMemo } from 'react';
import { useRealTimeData } from '../hooks/useRealTimeData';
import { StatCard, WarningPanel, RingOverview } from '../components/dashboard';
import { Gauge, Activity, Zap, Target } from 'lucide-react';
import { cn } from '../lib/utils';
import { Button } from '../components/ui/Button';

const Dashboard: React.FC = () => {
    const {
        latestRing,
        activeWarnings,
        latestPrediction,
        isLoading,
        isConnected,
        lastUpdate
    } = useRealTimeData();

    // 从环数据派生统计指标
    const stats = useMemo(() => {
        if (!latestRing) return [];

        return [
            {
                title: '推进速度',
                value: latestRing.mean_advance_rate ?? 0,
                unit: 'mm/min',
                icon: Gauge,
                status: (latestRing.mean_advance_rate ?? 0) > 45 ? 'warning' : 'normal',
                trend: { value: 2.5, label: '较上环', direction: 'up' as const }
            },
            {
                title: '推力均值',
                value: (latestRing.mean_thrust ?? 0).toLocaleString(),
                unit: 'kN',
                icon: Activity,
                status: 'normal',
                trend: { value: -1.2, label: '较上环', direction: 'down' as const }
            },
            {
                title: '扭矩均值',
                value: (latestRing.mean_torque ?? 0).toLocaleString(),
                unit: 'kNm',
                icon: Zap,
                status: 'normal',
                trend: { value: 0.8, label: '较上环', direction: 'up' as const }
            },
            {
                title: '地表沉降',
                value: latestRing.settlement_value ?? '-',
                unit: 'mm',
                icon: Target,
                status: Math.abs(latestRing.settlement_value ?? 0) > 5 ? 'alarm' : 'normal',
                trend: { value: 0, label: '稳定', direction: 'neutral' as const }
            }
        ];
    }, [latestRing]);

    return (
        <div className="space-y-6">
            {/* 顶部标题区 */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                    <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
                        施工监控大屏
                        <span className={cn(
                            "w-2 h-2 rounded-full",
                            isConnected ? "bg-success" : "bg-error animate-pulse"
                        )} />
                    </h1>
                    <p className="text-text-secondary">
                        正在监控 第{latestRing?.ring_number ?? '--'}环 · 最后更新: {new Date(lastUpdate).toLocaleTimeString()}
                    </p>
                </div>
                <div className="flex gap-2">
                    {/* 操作按钮区 */}
                </div>
            </div>

            {/* KPI 卡片区 */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                {isLoading ? (
                    Array(4).fill(0).map((_, i) => (
                        <div key={i} className="h-32 rounded-xl bg-surface animate-pulse" />
                    ))
                ) : (
                    stats.map((stat, i) => (
                        // @ts-ignore - 动态字符串类型
                        <StatCard key={i} {...stat} />
                    ))
                )}
            </div>

            {/* 主内容区 */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 h-[500px]">
                {/* 左侧: 图表区 */}
                <div className="lg:col-span-2 flex flex-col gap-6">
                    {/* 图表占位 */}
                    <div className="flex-1 rounded-xl border border-border bg-surface p-6 flex flex-col items-center justify-center relative overflow-hidden group">
                        <div className="absolute inset-0 bg-gradient-to-br from-primary/5 to-transparent opacity-50" />
                        <Activity className="w-16 h-16 text-primary/20 mb-4 group-hover:scale-110 transition-transform duration-500" />
                        <h3 className="text-lg font-medium text-text-primary">轨迹偏差分析</h3>
                        <p className="text-text-secondary text-sm mb-4">实时图表将在后续版本中展示</p>
                        <Button variant="outline">查看详细分析</Button>
                    </div>

                    <div className="h-1/3 grid grid-cols-2 gap-4">
                        {/* AI预测卡片 */}
                        <div className="rounded-xl border border-border bg-surface p-6 flex flex-col justify-between">
                            <div>
                                <h3 className="text-sm font-medium text-text-secondary">AI预测 (下一环)</h3>
                                <div className="mt-2 flex items-baseline gap-2">
                                    <span className="text-2xl font-bold text-primary">
                                        {latestPrediction?.predicted_settlement?.toFixed(2) ?? '-'}
                                    </span>
                                    <span className="text-sm text-text-muted">mm 沉降</span>
                                </div>
                            </div>
                            <div className="w-full bg-background rounded-full h-1.5 mt-4">
                                <div className="bg-primary h-1.5 rounded-full" style={{ width: '70%' }}></div>
                            </div>
                        </div>

                        {/* 地层进度卡片 */}
                        <div className="rounded-xl border border-border bg-surface p-6 flex flex-col justify-between">
                            <div>
                                <h3 className="text-sm font-medium text-text-secondary">地层进度</h3>
                                <div className="mt-2 text-xl font-bold text-text-primary">
                                    软土层
                                </div>
                            </div>
                            <div className="text-sm text-text-muted">
                                第150环 - 第200环
                            </div>
                        </div>
                    </div>
                </div>

                {/* 右侧: 告警与环详情 */}
                <div className="flex flex-col gap-6">
                    <div className="flex-1 min-h-0">
                        <WarningPanel warnings={activeWarnings} isLoading={isLoading} />
                    </div>
                    <div className="h-auto">
                        <RingOverview data={latestRing || null} isLoading={isLoading} />
                    </div>
                </div>
            </div>
        </div>
    );
};

export default Dashboard;
