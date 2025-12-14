/**
 * T172: Parameter Time Series Chart Component
 * Multi-series time/ring-based parameter visualization
 */
import React, { useMemo, useCallback } from 'react';
import ReactECharts from 'echarts-for-react';
import type { EChartsOption } from 'echarts';
import type { TimeSeriesData, MultiSeriesData, TimeSeriesPoint } from '../../types/charts';
import {
  getBaseChartOptions,
  getValueAxis,
  getTimeAxis,
  createLineSeries,
  createThresholdMarkLine,
  getLegendConfig,
  getDataZoom,
  CHART_COLORS,
  SERIES_COLORS,
  WARNING_LEVEL_COLORS,
  createTimeTooltipFormatter,
  createRingTooltipFormatter,
} from '../../utils/chartConfig';

// ============================================================================
// Types
// ============================================================================

export interface ParameterTimeSeriesProps {
  data: MultiSeriesData | TimeSeriesData | null;
  title?: string;
  height?: number | string;
  showDataZoom?: boolean;
  showLegend?: boolean;
  thresholds?: {
    attention?: number;
    warning?: number;
    alarm?: number;
  };
  yAxisName?: string;
  yAxisUnit?: string;
  showArea?: boolean;
  smooth?: boolean;
  onPointClick?: (point: TimeSeriesPoint, seriesName: string) => void;
  loading?: boolean;
}

// ============================================================================
// Helper Functions
// ============================================================================

function normalizeToMultiSeries(data: MultiSeriesData | TimeSeriesData): MultiSeriesData {
  if ('series' in data) {
    return data;
  }
  return {
    series: [data],
    xAxisType: 'time',
  };
}

function seriesToChartData(
  series: TimeSeriesData,
  xAxisType: 'time' | 'ring'
): [number, number][] {
  return series.data.map((point) => [
    xAxisType === 'time' ? point.timestamp : (point.ring_number || 0),
    point.value,
  ]);
}

// ============================================================================
// Component
// ============================================================================

const ParameterTimeSeries: React.FC<ParameterTimeSeriesProps> = ({
  data,
  title,
  height = 300,
  showDataZoom = false,
  showLegend = true,
  thresholds,
  yAxisName,
  yAxisUnit,
  showArea = false,
  smooth = true,
  onPointClick,
  loading = false,
}) => {
  // Normalize data to multi-series format
  const normalizedData = useMemo(() => {
    if (!data) return null;
    return normalizeToMultiSeries(data);
  }, [data]);

  // Build series
  const chartSeries = useMemo(() => {
    if (!normalizedData) return [];

    return normalizedData.series.map((series, index) => {
      const color = series.color || SERIES_COLORS[index % SERIES_COLORS.length];
      const chartData = seriesToChartData(series, normalizedData.xAxisType);

      const seriesConfig = createLineSeries(series.label, chartData, color, {
        smooth,
        areaStyle: showArea,
        lineWidth: 2,
      });

      // Add threshold mark lines to first series only
      if (index === 0 && thresholds) {
        const markLines: object[] = [];

        if (thresholds.attention !== undefined) {
          markLines.push({
            yAxis: thresholds.attention,
            name: '注意',
            lineStyle: { color: WARNING_LEVEL_COLORS.ATTENTION, type: 'dashed' },
            label: { show: true, position: 'insideEndTop', color: WARNING_LEVEL_COLORS.ATTENTION },
          });
        }

        if (thresholds.warning !== undefined) {
          markLines.push({
            yAxis: thresholds.warning,
            name: '警告',
            lineStyle: { color: WARNING_LEVEL_COLORS.WARNING, type: 'dashed' },
            label: { show: true, position: 'insideEndTop', color: WARNING_LEVEL_COLORS.WARNING },
          });
        }

        if (thresholds.alarm !== undefined) {
          markLines.push({
            yAxis: thresholds.alarm,
            name: '报警',
            lineStyle: { color: WARNING_LEVEL_COLORS.ALARM, type: 'dashed' },
            label: { show: true, position: 'insideEndTop', color: WARNING_LEVEL_COLORS.ALARM },
          });
        }

        if (markLines.length > 0) {
          (seriesConfig as any).markLine = {
            silent: true,
            symbol: 'none',
            data: markLines,
          };
        }
      }

      return seriesConfig;
    });
  }, [normalizedData, smooth, showArea, thresholds]);

  // Legend items
  const legendItems = useMemo(() => {
    if (!normalizedData) return [];
    return normalizedData.series.map((s) => s.label);
  }, [normalizedData]);

  // Determine unit for tooltip
  const unit = useMemo(() => {
    if (yAxisUnit) return yAxisUnit;
    if (normalizedData?.series[0]?.unit) return normalizedData.series[0].unit;
    return '';
  }, [yAxisUnit, normalizedData]);

  // X-axis type
  const xAxisType = normalizedData?.xAxisType || 'time';

  // Chart options
  const options: EChartsOption = useMemo(() => {
    const baseOptions = getBaseChartOptions();

    return {
      ...baseOptions,
      ...(title && {
        title: {
          text: title,
          left: 'center',
          textStyle: {
            color: CHART_COLORS.text,
            fontSize: 14,
            fontWeight: 500,
          },
        },
      }),
      ...(showLegend && legendItems.length > 1 && {
        legend: {
          ...getLegendConfig(legendItems, 'top'),
          top: title ? 30 : 10,
        },
      }),
      grid: {
        ...baseOptions.grid,
        top: title ? (showLegend && legendItems.length > 1 ? 70 : 50) : (showLegend && legendItems.length > 1 ? 50 : 30),
        bottom: showDataZoom ? 60 : 30,
      },
      tooltip: {
        ...baseOptions.tooltip,
        formatter: xAxisType === 'time'
          ? createTimeTooltipFormatter(unit)
          : createRingTooltipFormatter(unit),
      },
      xAxis: xAxisType === 'time'
        ? getTimeAxis()
        : {
            ...getValueAxis({ min: 'dataMin', max: 'dataMax' }),
            name: '环号',
            nameTextStyle: { color: CHART_COLORS.text },
          },
      yAxis: getValueAxis({
        name: yAxisName || (normalizedData?.series[0]?.label ? `${normalizedData.series[0].label} (${unit})` : ''),
      }),
      series: chartSeries,
      ...(showDataZoom && { dataZoom: getDataZoom('both') }),
    };
  }, [
    title,
    showLegend,
    legendItems,
    showDataZoom,
    xAxisType,
    unit,
    yAxisName,
    normalizedData,
    chartSeries,
  ]);

  // Handle click events
  const handleChartClick = useCallback(
    (params: any) => {
      if (onPointClick && params.data && normalizedData) {
        const [xValue, yValue] = params.data;
        const point: TimeSeriesPoint =
          xAxisType === 'time'
            ? { timestamp: xValue, value: yValue }
            : { timestamp: Date.now(), value: yValue, ring_number: xValue };
        onPointClick(point, params.seriesName);
      }
    },
    [onPointClick, normalizedData, xAxisType]
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
        暂无数据
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

export default ParameterTimeSeries;
