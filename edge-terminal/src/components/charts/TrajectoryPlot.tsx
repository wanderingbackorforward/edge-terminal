/**
 * T170: Trajectory Deviation Plot Component
 * Displays actual vs design trajectory with tolerance bands
 */
import React, { useMemo, useCallback } from 'react';
import ReactECharts from 'echarts-for-react';
import type { EChartsOption } from 'echarts';
import type { TrajectoryData, TrajectoryPoint } from '../../types/charts';
import {
  getBaseChartOptions,
  getValueAxis,
  createLineSeries,
  createToleranceBand,
  getLegendConfig,
  getDataZoom,
  CHART_COLORS,
  createRingTooltipFormatter,
} from '../../utils/chartConfig';

// ============================================================================
// Types
// ============================================================================

export interface TrajectoryPlotProps {
  data: TrajectoryData | null;
  title?: string;
  height?: number | string;
  showHorizontal?: boolean;
  showVertical?: boolean;
  showTolerance?: boolean;
  showDataZoom?: boolean;
  onRingClick?: (ringNumber: number) => void;
  loading?: boolean;
}

type Direction = 'horizontal' | 'vertical';

// ============================================================================
// Helper Functions
// ============================================================================

function trajectoryToData(points: TrajectoryPoint[], direction: Direction): [number, number][] {
  return points.map((p) => [
    p.ring_number,
    direction === 'horizontal' ? p.horizontal : p.vertical,
  ]);
}

// ============================================================================
// Component
// ============================================================================

const TrajectoryPlot: React.FC<TrajectoryPlotProps> = ({
  data,
  title = '轨迹偏差',
  height = 400,
  showHorizontal = true,
  showVertical = true,
  showTolerance = true,
  showDataZoom = true,
  onRingClick,
  loading = false,
}) => {
  // Process data into chart format
  const chartData = useMemo(() => {
    if (!data) return null;

    return {
      actualHorizontal: trajectoryToData(data.actual, 'horizontal'),
      actualVertical: trajectoryToData(data.actual, 'vertical'),
      designHorizontal: trajectoryToData(data.design, 'horizontal'),
      designVertical: trajectoryToData(data.design, 'vertical'),
      toleranceUpperH: trajectoryToData(data.tolerance_upper, 'horizontal'),
      toleranceLowerH: trajectoryToData(data.tolerance_lower, 'horizontal'),
      toleranceUpperV: trajectoryToData(data.tolerance_upper, 'vertical'),
      toleranceLowerV: trajectoryToData(data.tolerance_lower, 'vertical'),
    };
  }, [data]);

  // Build series array
  const series = useMemo(() => {
    if (!chartData) return [];

    const result: object[] = [];

    // Horizontal deviation
    if (showHorizontal) {
      result.push(
        createLineSeries('水平偏差(实际)', chartData.actualHorizontal, CHART_COLORS.primary, {
          smooth: true,
          lineWidth: 2,
        })
      );
      result.push(
        createLineSeries('水平偏差(设计)', chartData.designHorizontal, CHART_COLORS.primary, {
          smooth: true,
          lineWidth: 1,
          dashStyle: 'dashed',
        })
      );

      if (showTolerance) {
        result.push(
          ...createToleranceBand(
            chartData.toleranceUpperH,
            chartData.toleranceLowerH,
            CHART_COLORS.attention,
            '水平容差'
          )
        );
      }
    }

    // Vertical deviation
    if (showVertical) {
      result.push(
        createLineSeries('垂直偏差(实际)', chartData.actualVertical, CHART_COLORS.secondary, {
          smooth: true,
          lineWidth: 2,
        })
      );
      result.push(
        createLineSeries('垂直偏差(设计)', chartData.designVertical, CHART_COLORS.secondary, {
          smooth: true,
          lineWidth: 1,
          dashStyle: 'dashed',
        })
      );

      if (showTolerance) {
        result.push(
          ...createToleranceBand(
            chartData.toleranceUpperV,
            chartData.toleranceLowerV,
            CHART_COLORS.warning,
            '垂直容差'
          )
        );
      }
    }

    return result;
  }, [chartData, showHorizontal, showVertical, showTolerance]);

  // Build legend items
  const legendItems = useMemo(() => {
    const items: string[] = [];
    if (showHorizontal) {
      items.push('水平偏差(实际)', '水平偏差(设计)');
    }
    if (showVertical) {
      items.push('垂直偏差(实际)', '垂直偏差(设计)');
    }
    return items;
  }, [showHorizontal, showVertical]);

  // Chart options
  const options: EChartsOption = useMemo(() => {
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
      legend: getLegendConfig(legendItems, 'top'),
      grid: {
        ...baseOptions.grid,
        top: 80,
        bottom: showDataZoom ? 60 : 40,
      },
      tooltip: {
        ...baseOptions.tooltip,
        formatter: createRingTooltipFormatter('mm'),
      },
      xAxis: {
        ...getValueAxis({ name: '环号', min: 'dataMin', max: 'dataMax' }),
        type: 'value',
      },
      yAxis: getValueAxis({ name: '偏差 (mm)' }),
      series,
      ...(showDataZoom && { dataZoom: getDataZoom('both') }),
    };
  }, [title, legendItems, series, showDataZoom]);

  // Handle chart click events
  const handleChartClick = useCallback(
    (params: any) => {
      if (onRingClick && params.data) {
        const ringNumber = Array.isArray(params.data) ? params.data[0] : params.name;
        onRingClick(ringNumber);
      }
    },
    [onRingClick]
  );

  // Event handlers for ECharts
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
        暂无轨迹数据
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

export default TrajectoryPlot;
