/**
 * T170: ECharts Configuration Utilities
 * Shared chart configurations and theme settings
 */
import type { EChartsOption } from 'echarts';
import type { ChartTheme, ChartColors, AxisConfig, TooltipConfig } from '../types/charts';

// ============================================================================
// Color Palette
// ============================================================================

export const CHART_COLORS: ChartColors = {
  primary: '#1890ff',
  secondary: '#52c41a',
  attention: '#faad14',
  warning: '#fa8c16',
  alarm: '#f5222d',
  success: '#52c41a',
  background: '#141414',
  grid: '#303030',
  text: '#d9d9d9',
};

// Extended color palette for multi-series charts
export const SERIES_COLORS = [
  '#1890ff', // Blue
  '#52c41a', // Green
  '#722ed1', // Purple
  '#13c2c2', // Cyan
  '#fa8c16', // Orange
  '#eb2f96', // Magenta
  '#a0d911', // Lime
  '#faad14', // Gold
];

// Warning level colors
export const WARNING_LEVEL_COLORS = {
  ATTENTION: '#faad14',
  WARNING: '#fa8c16',
  ALARM: '#f5222d',
  NORMAL: '#52c41a',
};

// ============================================================================
// Chart Theme
// ============================================================================

export const DARK_THEME: ChartTheme = {
  colors: CHART_COLORS,
  backgroundColor: 'transparent',
  textStyle: {
    color: '#d9d9d9',
    fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
  },
  animation: true,
};

// ============================================================================
// Base Chart Options
// ============================================================================

export function getBaseChartOptions(): Partial<EChartsOption> {
  return {
    backgroundColor: DARK_THEME.backgroundColor,
    textStyle: DARK_THEME.textStyle,
    grid: {
      left: 60,
      right: 40,
      top: 40,
      bottom: 40,
      containLabel: true,
    },
    tooltip: {
      show: true,
      trigger: 'axis',
      backgroundColor: 'rgba(20, 20, 20, 0.9)',
      borderColor: '#303030',
      textStyle: {
        color: '#d9d9d9',
      },
    },
  };
}

// ============================================================================
// Axis Configurations
// ============================================================================

export function getValueAxis(config: Partial<AxisConfig> = {}): object {
  return {
    type: 'value',
    name: config.name || '',
    nameTextStyle: {
      color: CHART_COLORS.text,
      padding: [0, 0, 0, 40],
    },
    min: config.min,
    max: config.max,
    interval: config.interval,
    axisLine: {
      show: true,
      lineStyle: {
        color: CHART_COLORS.grid,
      },
    },
    axisTick: {
      show: true,
      lineStyle: {
        color: CHART_COLORS.grid,
      },
    },
    axisLabel: {
      color: CHART_COLORS.text,
    },
    splitLine: {
      show: true,
      lineStyle: {
        color: CHART_COLORS.grid,
        type: 'dashed',
      },
    },
  };
}

export function getCategoryAxis(categories: string[], config: Partial<AxisConfig> = {}): object {
  return {
    type: 'category',
    name: config.name || '',
    nameTextStyle: {
      color: CHART_COLORS.text,
    },
    data: categories,
    axisLine: {
      show: true,
      lineStyle: {
        color: CHART_COLORS.grid,
      },
    },
    axisTick: {
      show: true,
      lineStyle: {
        color: CHART_COLORS.grid,
      },
    },
    axisLabel: {
      color: CHART_COLORS.text,
    },
  };
}

export function getTimeAxis(config: Partial<AxisConfig> = {}): object {
  return {
    type: 'time',
    name: config.name || '',
    nameTextStyle: {
      color: CHART_COLORS.text,
    },
    axisLine: {
      show: true,
      lineStyle: {
        color: CHART_COLORS.grid,
      },
    },
    axisTick: {
      show: true,
      lineStyle: {
        color: CHART_COLORS.grid,
      },
    },
    axisLabel: {
      color: CHART_COLORS.text,
      formatter: '{HH}:{mm}',
    },
    splitLine: {
      show: true,
      lineStyle: {
        color: CHART_COLORS.grid,
        type: 'dashed',
      },
    },
  };
}

// ============================================================================
// Tooltip Formatters
// ============================================================================

export function formatTooltipValue(value: number, unit: string, decimals: number = 2): string {
  return `${value.toFixed(decimals)} ${unit}`;
}

export function formatTimestamp(timestamp: number): string {
  const date = new Date(timestamp);
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

export function createRingTooltipFormatter(unit: string): (params: any) => string {
  return (params: any) => {
    if (Array.isArray(params)) {
      let result = `<strong>环号: ${params[0]?.value?.[0] || params[0]?.name}</strong><br/>`;
      params.forEach((item: any) => {
        const value = Array.isArray(item.value) ? item.value[1] : item.value;
        result += `${item.marker} ${item.seriesName}: ${formatTooltipValue(value, unit)}<br/>`;
      });
      return result;
    }
    const value = Array.isArray(params.value) ? params.value[1] : params.value;
    return `${params.marker} ${params.seriesName}: ${formatTooltipValue(value, unit)}`;
  };
}

export function createTimeTooltipFormatter(unit: string): (params: any) => string {
  return (params: any) => {
    if (Array.isArray(params)) {
      let result = `<strong>${formatTimestamp(params[0]?.value?.[0])}</strong><br/>`;
      params.forEach((item: any) => {
        const value = Array.isArray(item.value) ? item.value[1] : item.value;
        result += `${item.marker} ${item.seriesName}: ${formatTooltipValue(value, unit)}<br/>`;
      });
      return result;
    }
    const value = Array.isArray(params.value) ? params.value[1] : params.value;
    return `${params.marker} ${params.seriesName}: ${formatTooltipValue(value, unit)}`;
  };
}

// ============================================================================
// Series Generators
// ============================================================================

export function createLineSeries(
  name: string,
  data: [number, number][],
  color: string,
  options: {
    smooth?: boolean;
    showSymbol?: boolean;
    lineWidth?: number;
    areaStyle?: boolean;
    dashStyle?: 'solid' | 'dashed' | 'dotted';
  } = {}
): object {
  const {
    smooth = true,
    showSymbol = false,
    lineWidth = 2,
    areaStyle = false,
    dashStyle = 'solid',
  } = options;

  return {
    name,
    type: 'line',
    data,
    smooth,
    showSymbol,
    lineStyle: {
      color,
      width: lineWidth,
      type: dashStyle,
    },
    itemStyle: {
      color,
    },
    ...(areaStyle && {
      areaStyle: {
        color: {
          type: 'linear',
          x: 0,
          y: 0,
          x2: 0,
          y2: 1,
          colorStops: [
            { offset: 0, color: `${color}40` },
            { offset: 1, color: `${color}05` },
          ],
        },
      },
    }),
  };
}

export function createScatterSeries(
  name: string,
  data: [number, number][],
  color: string,
  symbolSize: number = 8
): object {
  return {
    name,
    type: 'scatter',
    data,
    symbolSize,
    itemStyle: {
      color,
    },
  };
}

export function createBarSeries(
  name: string,
  data: number[],
  color: string,
  options: {
    barWidth?: number | string;
    showBackground?: boolean;
  } = {}
): object {
  const { barWidth = '60%', showBackground = false } = options;

  return {
    name,
    type: 'bar',
    data,
    barWidth,
    itemStyle: {
      color,
      borderRadius: [4, 4, 0, 0],
    },
    ...(showBackground && {
      showBackground: true,
      backgroundStyle: {
        color: 'rgba(255, 255, 255, 0.05)',
        borderRadius: [4, 4, 0, 0],
      },
    }),
  };
}

// ============================================================================
// Mark Lines and Areas
// ============================================================================

export function createThresholdMarkLine(
  value: number,
  name: string,
  color: string
): object {
  return {
    silent: true,
    symbol: 'none',
    lineStyle: {
      color,
      type: 'dashed',
      width: 1,
    },
    label: {
      show: true,
      position: 'insideEndTop',
      formatter: `${name}: {c}`,
      color,
      fontSize: 10,
    },
    data: [
      {
        yAxis: value,
        name,
      },
    ],
  };
}

export function createToleranceBand(
  upperData: [number, number][],
  lowerData: [number, number][],
  color: string,
  name: string = '容差带'
): object[] {
  return [
    {
      name: `${name}上限`,
      type: 'line',
      data: upperData,
      lineStyle: {
        color,
        type: 'dashed',
        width: 1,
      },
      showSymbol: false,
      emphasis: { disabled: true },
    },
    {
      name: `${name}下限`,
      type: 'line',
      data: lowerData,
      lineStyle: {
        color,
        type: 'dashed',
        width: 1,
      },
      showSymbol: false,
      areaStyle: {
        color: 'transparent',
      },
      emphasis: { disabled: true },
    },
  ];
}

// ============================================================================
// Legend Configuration
// ============================================================================

export function getLegendConfig(items: string[], position: 'top' | 'bottom' = 'top'): object {
  return {
    show: true,
    data: items,
    orient: 'horizontal',
    left: 'center',
    top: position === 'top' ? 10 : 'auto',
    bottom: position === 'bottom' ? 10 : 'auto',
    textStyle: {
      color: CHART_COLORS.text,
    },
    itemStyle: {
      borderWidth: 0,
    },
  };
}

// ============================================================================
// Data Zoom Configuration
// ============================================================================

export function getDataZoom(type: 'slider' | 'inside' | 'both' = 'both'): object[] {
  const result: object[] = [];

  if (type === 'slider' || type === 'both') {
    result.push({
      type: 'slider',
      show: true,
      xAxisIndex: 0,
      bottom: 10,
      height: 20,
      borderColor: CHART_COLORS.grid,
      fillerColor: 'rgba(24, 144, 255, 0.2)',
      handleStyle: {
        color: CHART_COLORS.primary,
      },
      textStyle: {
        color: CHART_COLORS.text,
      },
    });
  }

  if (type === 'inside' || type === 'both') {
    result.push({
      type: 'inside',
      xAxisIndex: 0,
    });
  }

  return result;
}

// ============================================================================
// Visual Map for Heatmaps
// ============================================================================

export function getHeatmapVisualMap(
  min: number,
  max: number,
  colors: string[] = ['#313695', '#4575b4', '#74add1', '#abd9e9', '#e0f3f8', '#ffffbf', '#fee090', '#fdae61', '#f46d43', '#d73027', '#a50026']
): object {
  return {
    min,
    max,
    calculable: true,
    orient: 'horizontal',
    left: 'center',
    bottom: 10,
    inRange: {
      color: colors,
    },
    textStyle: {
      color: CHART_COLORS.text,
    },
  };
}

export function getWarningLevelVisualMap(): object {
  return {
    show: false,
    pieces: [
      { value: 0, color: CHART_COLORS.grid, label: '无' },
      { value: 1, color: WARNING_LEVEL_COLORS.ATTENTION, label: '注意' },
      { value: 2, color: WARNING_LEVEL_COLORS.WARNING, label: '警告' },
      { value: 3, color: WARNING_LEVEL_COLORS.ALARM, label: '报警' },
    ],
  };
}

// ============================================================================
// Export default config
// ============================================================================

export default {
  colors: CHART_COLORS,
  seriesColors: SERIES_COLORS,
  warningColors: WARNING_LEVEL_COLORS,
  theme: DARK_THEME,
  getBaseChartOptions,
  getValueAxis,
  getCategoryAxis,
  getTimeAxis,
  createLineSeries,
  createScatterSeries,
  createBarSeries,
  createThresholdMarkLine,
  createToleranceBand,
  getLegendConfig,
  getDataZoom,
  getHeatmapVisualMap,
  getWarningLevelVisualMap,
};
