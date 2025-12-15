import React, { useMemo } from 'react';
import { BaseChart } from './BaseChart';
import { RingSummary } from '../../types/api';

interface TrajectoryChartProps {
    data: RingSummary[];
    isLoading?: boolean;
}

export const TrajectoryChart: React.FC<TrajectoryChartProps> = ({ data, isLoading }) => {
    const options = useMemo(() => {
        // Process data for charts
        const chartData = data
            .sort((a, b) => a.ring_number - b.ring_number)
            .map(r => ({
                ring: r.ring_number,
                hDev: r.horizontal_deviation ?? 0,
                vDev: r.vertical_deviation ?? 0,
            }));

        return {
            tooltip: {
                trigger: 'axis',
                axisPointer: { type: 'cross' }
            },
            legend: {
                data: ['水平偏差', '垂直偏差'],
                bottom: 0,
            },
            grid: {
                top: 30,
                right: 30,
                bottom: 30,
                left: 40,
                containLabel: true,
            },
            xAxis: {
                type: 'category',
                data: chartData.map(d => d.ring),
                name: '环号',
                nameLocation: 'middle',
                nameGap: 30,
            },
            yAxis: {
                type: 'value',
                name: '偏差 (mm)',
                splitLine: {
                    lineStyle: {
                        type: 'dashed',
                        color: '#30363d'
                    }
                }
            },
            series: [
                {
                    name: '水平偏差',
                    type: 'line',
                    data: chartData.map(d => d.hDev),
                    smooth: true,
                    itemStyle: { color: '#58a6ff' },
                    areaStyle: {
                        color: {
                            type: 'linear',
                            x: 0, y: 0, x2: 0, y2: 1,
                            colorStops: [
                                { offset: 0, color: 'rgba(88, 166, 255, 0.2)' },
                                { offset: 1, color: 'rgba(88, 166, 255, 0)' }
                            ]
                        }
                    }
                },
                {
                    name: '垂直偏差',
                    type: 'line',
                    data: chartData.map(d => d.vDev),
                    smooth: true,
                    itemStyle: { color: '#3fb950' },
                    areaStyle: {
                        color: {
                            type: 'linear',
                            x: 0, y: 0, x2: 0, y2: 1,
                            colorStops: [
                                { offset: 0, color: 'rgba(63, 185, 80, 0.2)' },
                                { offset: 1, color: 'rgba(63, 185, 80, 0)' }
                            ]
                        }
                    }
                }
            ]
        };
    }, [data]);

    return <BaseChart options={options} isLoading={isLoading} height="350px" />;
};
