import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ringApi } from '../services/api';
import { TrajectoryChart, TrendChart } from '../components/charts';
import { Card, CardHeader, CardTitle, CardContent } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Calendar, Download } from 'lucide-react';

const Analytics: React.FC = () => {
    const [range, setRange] = useState({ start: 1, end: 100 });

    const { data: rings, isLoading } = useQuery({
        queryKey: ['rings', 'range', range.start, range.end],
        queryFn: () => ringApi.getRingRange(range.start, range.end),
        staleTime: 60000, // 1分钟缓存
    });

    return (
        <div className="space-y-6">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                    <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
                        数据分析
                    </h1>
                    <p className="text-text-secondary">
                        历史趋势与轨迹分析
                    </p>
                </div>
                <div className="flex gap-2">
                    <Button variant="outline" size="sm">
                        <Calendar className="w-4 h-4 mr-2" />
                        第{range.start}环 - 第{range.end}环
                    </Button>
                    <Button variant="outline" size="sm">
                        <Download className="w-4 h-4 mr-2" />
                        导出报告
                    </Button>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* 轨迹分析 */}
                <Card className="lg:col-span-2">
                    <CardHeader>
                        <CardTitle>隧道轨迹偏差</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <TrajectoryChart data={rings || []} isLoading={isLoading} />
                    </CardContent>
                </Card>

                {/* 推力趋势 */}
                <Card>
                    <CardHeader>
                        <CardTitle>推力趋势</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <TrendChart
                            data={rings || []}
                            parameter="mean_thrust"
                            label="推力"
                            unit="kN"
                            color="#58a6ff"
                            isLoading={isLoading}
                        />
                    </CardContent>
                </Card>

                {/* 扭矩趋势 */}
                <Card>
                    <CardHeader>
                        <CardTitle>刀盘扭矩趋势</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <TrendChart
                            data={rings || []}
                            parameter="mean_torque"
                            label="扭矩"
                            unit="kNm"
                            color="#d29922"
                            isLoading={isLoading}
                        />
                    </CardContent>
                </Card>

                {/* 沉降趋势 */}
                <Card className="lg:col-span-2">
                    <CardHeader>
                        <CardTitle>地表沉降监测</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <TrendChart
                            data={rings || []}
                            parameter="settlement_value"
                            label="沉降"
                            unit="mm"
                            color="#f85149"
                            isLoading={isLoading}
                        />
                    </CardContent>
                </Card>
            </div>
        </div>
    );
};

export default Analytics;
