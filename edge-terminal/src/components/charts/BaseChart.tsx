import React, { useRef, useEffect } from 'react';
import ReactECharts from 'echarts-for-react';
import * as echarts from 'echarts';

interface BaseChartProps {
    options: any;
    height?: string | number;
    isLoading?: boolean;
    className?: string;
}

// Dark theme configuration
const darkTheme = {
    backgroundColor: 'transparent',
    textStyle: { color: '#8b949e' },
    title: { textStyle: { color: '#c9d1d9' } },
    line: { itemStyle: { borderWidth: 2 } },
    categoryAxis: {
        axisLine: { lineStyle: { color: '#30363d' } },
        axisTick: { show: false },
        axisLabel: { color: '#8b949e' },
        splitLine: { show: false },
    },
    valueAxis: {
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: { color: '#8b949e' },
        splitLine: { lineStyle: { color: '#30363d', type: 'dashed' } },
    },
    tooltip: {
        backgroundColor: '#161b22',
        borderColor: '#30363d',
        textStyle: { color: '#c9d1d9' },
    },
    legend: { textStyle: { color: '#8b949e' } },
};

echarts.registerTheme('dark-custom', darkTheme);

export const BaseChart: React.FC<BaseChartProps> = ({
    options,
    height = '300px',
    isLoading,
    className
}) => {
    return (
        <div className={className}>
            <ReactECharts
                option={options}
                style={{ height, width: '100%' }}
                theme="dark-custom"
                showLoading={isLoading}
                loadingOption={{
                    text: '',
                    color: '#58a6ff',
                    textColor: '#c9d1d9',
                    maskColor: 'rgba(22, 27, 34, 0.8)',
                }}
            />
        </div>
    );
};
