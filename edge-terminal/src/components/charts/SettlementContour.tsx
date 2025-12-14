/**
 * T171: Settlement Contour/Heatmap Component
 * Displays ground settlement distribution as heatmap
 */
import React, { useMemo, useCallback } from 'react';
import ReactECharts from 'echarts-for-react';
import type { EChartsOption } from 'echarts';
import type { SettlementContourData, SettlementPoint } from '../../types/charts';
import {
  getBaseChartOptions,
  getValueAxis,
  getHeatmapVisualMap,
  CHART_COLORS,
  formatTooltipValue,
} from '../../utils/chartConfig';

// ============================================================================
// Types
// ============================================================================

export interface SettlementContourProps {
  data: SettlementContourData | null;
  title?: string;
  height?: number | string;
  showVisualMap?: boolean;
  showLabels?: boolean;
  gridSize?: number;
  thresholds?: {
    attention: number;
    warning: number;
    alarm: number;
  };
  onPointClick?: (point: SettlementPoint) => void;
  loading?: boolean;
}

// Default settlement thresholds (mm)
const DEFAULT_THRESHOLDS = {
  attention: -15,
  warning: -25,
  alarm: -35,
};

// Settlement color scale (blue = uplift, yellow/red = settlement)
const SETTLEMENT_COLORS = [
  '#313695', // Deep blue (uplift)
  '#4575b4',
  '#74add1',
  '#abd9e9',
  '#e0f3f8',
  '#ffffbf', // Yellow (neutral)
  '#fee090',
  '#fdae61',
  '#f46d43',
  '#d73027',
  '#a50026', // Deep red (high settlement)
];

// ============================================================================
// Helper Functions
// ============================================================================

function processHeatmapData(
  points: SettlementPoint[],
  gridSize: number
): { data: [number, number, number][]; xCategories: number[]; yCategories: number[] } {
  if (!points.length) {
    return { data: [], xCategories: [], yCategories: [] };
  }

  // Get bounds
  const xValues = points.map((p) => p.x);
  const yValues = points.map((p) => p.y);
  const minX = Math.min(...xValues);
  const maxX = Math.max(...xValues);
  const minY = Math.min(...yValues);
  const maxY = Math.max(...yValues);

  // Create grid
  const xBins = Math.ceil((maxX - minX) / gridSize) || 1;
  const yBins = Math.ceil((maxY - minY) / gridSize) || 1;

  // Create category arrays
  const xCategories: number[] = [];
  const yCategories: number[] = [];
  for (let i = 0; i <= xBins; i++) {
    xCategories.push(Math.round((minX + i * gridSize) * 10) / 10);
  }
  for (let i = 0; i <= yBins; i++) {
    yCategories.push(Math.round((minY + i * gridSize) * 10) / 10);
  }

  // Create grid accumulator
  const grid: Map<string, { sum: number; count: number }> = new Map();

  // Bin points
  points.forEach((point) => {
    const xIdx = Math.floor((point.x - minX) / gridSize);
    const yIdx = Math.floor((point.y - minY) / gridSize);
    const key = `${xIdx},${yIdx}`;

    if (!grid.has(key)) {
      grid.set(key, { sum: 0, count: 0 });
    }
    const cell = grid.get(key)!;
    cell.sum += point.settlement;
    cell.count += 1;
  });

  // Convert to heatmap data
  const data: [number, number, number][] = [];
  grid.forEach((value, key) => {
    const [xIdx, yIdx] = key.split(',').map(Number);
    const avgSettlement = value.sum / value.count;
    data.push([xIdx, yIdx, Math.round(avgSettlement * 100) / 100]);
  });

  return { data, xCategories, yCategories };
}

// ============================================================================
// Component
// ============================================================================

const SettlementContour: React.FC<SettlementContourProps> = ({
  data,
  title = '地表沉降分布',
  height = 400,
  showVisualMap = true,
  showLabels = false,
  gridSize = 5,
  thresholds = DEFAULT_THRESHOLDS,
  onPointClick,
  loading = false,
}) => {
  // Process data into heatmap format
  const heatmapData = useMemo(() => {
    if (!data?.points) return null;
    return processHeatmapData(data.points, gridSize);
  }, [data, gridSize]);

  // Build visual map config
  const visualMapConfig = useMemo(() => {
    if (!data || !showVisualMap) return undefined;

    return {
      ...getHeatmapVisualMap(data.minSettlement, data.maxSettlement, SETTLEMENT_COLORS),
      formatter: (value: number) => `${value.toFixed(1)} mm`,
    };
  }, [data, showVisualMap]);

  // Chart options
  const options: EChartsOption = useMemo(() => {
    if (!heatmapData) return {};

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
        bottom: showVisualMap ? 80 : 40,
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
          const [xIdx, yIdx, value] = params.data;
          const x = heatmapData.xCategories[xIdx];
          const y = heatmapData.yCategories[yIdx];
          const level = getSettlementLevel(value, thresholds);
          return `
            <strong>位置</strong><br/>
            X: ${x} m<br/>
            Y: ${y} m<br/>
            沉降: ${formatTooltipValue(value, 'mm')}<br/>
            状态: <span style="color: ${level.color}">${level.label}</span>
          `;
        },
      },
      xAxis: {
        type: 'category',
        name: '沿隧道轴线 (m)',
        nameTextStyle: { color: CHART_COLORS.text },
        data: heatmapData.xCategories,
        splitArea: { show: true },
        axisLine: { lineStyle: { color: CHART_COLORS.grid } },
        axisLabel: { color: CHART_COLORS.text },
      },
      yAxis: {
        type: 'category',
        name: '横向距离 (m)',
        nameTextStyle: { color: CHART_COLORS.text },
        data: heatmapData.yCategories,
        splitArea: { show: true },
        axisLine: { lineStyle: { color: CHART_COLORS.grid } },
        axisLabel: { color: CHART_COLORS.text },
      },
      visualMap: visualMapConfig,
      series: [
        {
          name: '沉降',
          type: 'heatmap',
          data: heatmapData.data,
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
          ...(showLabels && {
            label: {
              show: true,
              formatter: (params: any) => params.data[2].toFixed(1),
              fontSize: 10,
              color: '#fff',
            },
          }),
        },
      ],
    };
  }, [heatmapData, title, showVisualMap, showLabels, visualMapConfig, thresholds]);

  // Handle chart click events
  const handleChartClick = useCallback(
    (params: any) => {
      if (onPointClick && params.data && heatmapData) {
        const [xIdx, yIdx, settlement] = params.data;
        onPointClick({
          x: heatmapData.xCategories[xIdx],
          y: heatmapData.yCategories[yIdx],
          settlement,
        });
      }
    },
    [onPointClick, heatmapData]
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
        暂无沉降数据
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

// ============================================================================
// Helper: Get settlement level
// ============================================================================

function getSettlementLevel(
  value: number,
  thresholds: { attention: number; warning: number; alarm: number }
): { label: string; color: string } {
  if (value <= thresholds.alarm) {
    return { label: '报警', color: CHART_COLORS.alarm };
  }
  if (value <= thresholds.warning) {
    return { label: '警告', color: CHART_COLORS.warning };
  }
  if (value <= thresholds.attention) {
    return { label: '注意', color: CHART_COLORS.attention };
  }
  return { label: '正常', color: CHART_COLORS.success };
}

export default SettlementContour;
