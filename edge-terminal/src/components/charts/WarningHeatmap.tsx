/**
 * T173: Warning Heatmap Component
 * Shows warning distribution across rings and indicators
 */
import React, { useMemo, useCallback } from 'react';
import ReactECharts from 'echarts-for-react';
import type { EChartsOption } from 'echarts';
import type { WarningHeatmapData, WarningHeatmapCell } from '../../types/charts';
import {
  getBaseChartOptions,
  CHART_COLORS,
  WARNING_LEVEL_COLORS,
} from '../../utils/chartConfig';

// ============================================================================
// Types
// ============================================================================

export interface WarningHeatmapProps {
  data: WarningHeatmapData | null;
  title?: string;
  height?: number | string;
  showCounts?: boolean;
  onCellClick?: (cell: WarningHeatmapCell) => void;
  loading?: boolean;
}

// ============================================================================
// Helper Functions
// ============================================================================

function levelToValue(level: 'ATTENTION' | 'WARNING' | 'ALARM' | null): number {
  switch (level) {
    case 'ALARM':
      return 3;
    case 'WARNING':
      return 2;
    case 'ATTENTION':
      return 1;
    default:
      return 0;
  }
}

function valueToLevel(value: number): 'ATTENTION' | 'WARNING' | 'ALARM' | null {
  switch (value) {
    case 3:
      return 'ALARM';
    case 2:
      return 'WARNING';
    case 1:
      return 'ATTENTION';
    default:
      return null;
  }
}

function getLevelLabel(level: 'ATTENTION' | 'WARNING' | 'ALARM' | null): string {
  switch (level) {
    case 'ALARM':
      return '报警';
    case 'WARNING':
      return '警告';
    case 'ATTENTION':
      return '注意';
    default:
      return '正常';
  }
}

function getLevelColor(level: 'ATTENTION' | 'WARNING' | 'ALARM' | null): string {
  switch (level) {
    case 'ALARM':
      return WARNING_LEVEL_COLORS.ALARM;
    case 'WARNING':
      return WARNING_LEVEL_COLORS.WARNING;
    case 'ATTENTION':
      return WARNING_LEVEL_COLORS.ATTENTION;
    default:
      return CHART_COLORS.grid;
  }
}

// Indicator name translations
const INDICATOR_LABELS: Record<string, string> = {
  thrust_mean: '推力均值',
  thrust_variance: '推力方差',
  earth_pressure: '土压力',
  grouting_pressure: '注浆压力',
  advance_rate: '推进速度',
  cutter_torque: '刀盘扭矩',
  settlement: '沉降',
  horizontal_deviation: '水平偏差',
  vertical_deviation: '垂直偏差',
  deviation_combined: '组合偏差',
};

// ============================================================================
// Component
// ============================================================================

const WarningHeatmap: React.FC<WarningHeatmapProps> = ({
  data,
  title = '告警分布热力图',
  height = 350,
  showCounts = true,
  onCellClick,
  loading = false,
}) => {
  // Process data into heatmap format
  const processedData = useMemo(() => {
    if (!data) return null;

    const rings: number[] = [];
    for (let r = data.ringRange[0]; r <= data.ringRange[1]; r++) {
      rings.push(r);
    }

    // Convert to [ringIdx, indicatorIdx, level, count] format
    const heatmapData: [number, number, number, number][] = [];
    const cellMap = new Map<string, WarningHeatmapCell>();

    data.cells.forEach((cell) => {
      cellMap.set(`${cell.ring_number}-${cell.indicator}`, cell);
    });

    rings.forEach((ring, ringIdx) => {
      data.indicators.forEach((indicator, indicatorIdx) => {
        const cell = cellMap.get(`${ring}-${indicator}`);
        const level = cell ? levelToValue(cell.level) : 0;
        const count = cell?.count || 0;
        heatmapData.push([ringIdx, indicatorIdx, level, count]);
      });
    });

    return {
      rings,
      indicators: data.indicators,
      heatmapData,
    };
  }, [data]);

  // Chart options
  const options: EChartsOption = useMemo(() => {
    if (!processedData) return {};

    const baseOptions = getBaseChartOptions();

    return {
      ...baseOptions,
      title: {
        text: title,
        left: 'center',
        textStyle: {
          color: CHART_COLORS.text,
          fontSize: 16,
          fontWeight: 500,
        },
      },
      grid: {
        ...baseOptions.grid,
        top: 60,
        bottom: 60,
        left: 120,
      },
      tooltip: {
        show: true,
        trigger: 'item',
        backgroundColor: 'rgba(20, 20, 20, 0.9)',
        borderColor: '#303030',
        textStyle: {
          color: CHART_COLORS.text,
        },
        formatter: (params: any) => {
          const [ringIdx, indicatorIdx, levelValue, count] = params.data;
          const ring = processedData.rings[ringIdx];
          const indicator = processedData.indicators[indicatorIdx];
          const level = valueToLevel(levelValue);
          const levelLabel = getLevelLabel(level);
          const indicatorLabel = INDICATOR_LABELS[indicator] || indicator;

          return `
            <strong>环号: ${ring}</strong><br/>
            指标: ${indicatorLabel}<br/>
            状态: <span style="color: ${getLevelColor(level)}">${levelLabel}</span><br/>
            ${count > 0 ? `告警次数: ${count}` : ''}
          `;
        },
      },
      xAxis: {
        type: 'category',
        name: '环号',
        nameTextStyle: { color: CHART_COLORS.text },
        data: processedData.rings,
        splitArea: { show: true },
        axisLine: { lineStyle: { color: CHART_COLORS.grid } },
        axisLabel: {
          color: CHART_COLORS.text,
          interval: Math.floor(processedData.rings.length / 10),
        },
      },
      yAxis: {
        type: 'category',
        name: '指标',
        nameTextStyle: { color: CHART_COLORS.text },
        data: processedData.indicators.map((i) => INDICATOR_LABELS[i] || i),
        splitArea: { show: true },
        axisLine: { lineStyle: { color: CHART_COLORS.grid } },
        axisLabel: {
          color: CHART_COLORS.text,
        },
      },
      visualMap: {
        show: true,
        type: 'piecewise',
        pieces: [
          { value: 0, color: CHART_COLORS.grid, label: '正常' },
          { value: 1, color: WARNING_LEVEL_COLORS.ATTENTION, label: '注意' },
          { value: 2, color: WARNING_LEVEL_COLORS.WARNING, label: '警告' },
          { value: 3, color: WARNING_LEVEL_COLORS.ALARM, label: '报警' },
        ],
        orient: 'horizontal',
        left: 'center',
        bottom: 10,
        textStyle: {
          color: CHART_COLORS.text,
        },
      },
      series: [
        {
          name: '告警',
          type: 'heatmap',
          data: processedData.heatmapData,
          itemStyle: {
            borderColor: CHART_COLORS.background,
            borderWidth: 1,
          },
          emphasis: {
            itemStyle: {
              shadowBlur: 10,
              shadowColor: 'rgba(0, 0, 0, 0.5)',
            },
          },
          ...(showCounts && {
            label: {
              show: true,
              formatter: (params: any) => {
                const count = params.data[3];
                return count > 0 ? String(count) : '';
              },
              fontSize: 10,
              color: '#fff',
            },
          }),
        },
      ],
    };
  }, [processedData, title, showCounts]);

  // Handle click events
  const handleChartClick = useCallback(
    (params: any) => {
      if (onCellClick && params.data && processedData) {
        const [ringIdx, indicatorIdx, levelValue, count] = params.data;
        onCellClick({
          ring_number: processedData.rings[ringIdx],
          indicator: processedData.indicators[indicatorIdx],
          level: valueToLevel(levelValue),
          count,
        });
      }
    },
    [onCellClick, processedData]
  );

  const onEvents = useMemo(
    () => ({
      click: handleChartClick,
    }),
    [handleChartClick]
  );

  if (!data && !loading) {
    return (
      <div
        style={{
          height,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: CHART_COLORS.text,
          backgroundColor: 'rgba(20, 20, 20, 0.5)',
          borderRadius: 8,
        }}
      >
        暂无告警数据
      </div>
    );
  }

  return (
    <ReactECharts
      option={options}
      style={{ height, width: '100%' }}
      showLoading={loading}
      loadingOption={{
        text: '加载中...',
        color: CHART_COLORS.primary,
        textColor: CHART_COLORS.text,
        maskColor: 'rgba(20, 20, 20, 0.8)',
      }}
      onEvents={onEvents}
      notMerge={true}
      lazyUpdate={true}
    />
  );
};

export default WarningHeatmap;
