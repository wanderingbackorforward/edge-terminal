import React, { useMemo } from 'react';
import { BaseChart } from './BaseChart';
import { RingSummary } from '../../types/api';

interface TrendChartProps {
    data: RingSummary[];
    parameter: keyof RingSummary;
    label: string;
    unit: string;
    color?: string;
    isLoading?: boolean;
}

export const TrendChart: React.FC<TrendChartProps> = ({
    data,
    parameter,
    label,
    unit,
    color = '#d29922',
    isLoading
}) => {
    const options = useMemo(() => {
        const chartData = data
            .sort((a, b) => a.ring_number - b.ring_number)
            .map(r => ({
                ring: r.ring_number,
                value: r[parameter] as number ?? 0,
            }));

        return {
            tooltip: {
                trigger: 'axis',
                formatter: `{b}<br />{a}: {c} ${unit}`
            },
            grid: {
                top: 20,
                right: 20,
                bottom: 20,
                left: 50,
                containLabel: true,
            },
            xAxis: {
                type: 'category',
                data: chartData.map(d => d.ring),
            },
            yAxis: {
                type: 'value',
                name: unit,
                splitLine: {
                    lineStyle: {
                        type: 'dashed',
                        color: '#30363d'
                    }
                }
            },
            series: [
                {
                    name: label,
                    type: 'line',
                    data: chartData.map(d => d.value),
                    smooth: true,
                    showSymbol: false,
                    itemStyle: { color: color },
                    lineStyle: { width: 2 },
                }
            ]
        };
    }, [data, parameter, label, unit, color]);

    return <BaseChart options={options} isLoading={isLoading} height="200px" />;
};
