/**
 * T166: TypeScript types for chart data
 * Defines data structures for ECharts visualizations
 */

// ============================================================================
// Trajectory Plot Data
// ============================================================================

export interface TrajectoryPoint {
  ring_number: number;
  horizontal: number;  // mm
  vertical: number;    // mm
  timestamp: number;
}

export interface TrajectoryData {
  actual: TrajectoryPoint[];
  design: TrajectoryPoint[];
  tolerance_upper: TrajectoryPoint[];
  tolerance_lower: TrajectoryPoint[];
}

// ============================================================================
// Settlement Contour Data
// ============================================================================

export interface SettlementPoint {
  x: number;           // Position along tunnel axis (m)
  y: number;           // Position perpendicular to axis (m)
  settlement: number;  // mm
}

export interface SettlementContourData {
  points: SettlementPoint[];
  minSettlement: number;
  maxSettlement: number;
  colorScale: string[];
}

// ============================================================================
// Time Series Data
// ============================================================================

export interface TimeSeriesPoint {
  timestamp: number;
  value: number;
  ring_number?: number;
}

export interface TimeSeriesData {
  label: string;
  data: TimeSeriesPoint[];
  unit: string;
  color?: string;
}

export interface MultiSeriesData {
  series: TimeSeriesData[];
  xAxisType: 'time' | 'ring';
}

// ============================================================================
// Distribution Data (Histograms)
// ============================================================================

export interface HistogramBin {
  min: number;
  max: number;
  count: number;
  label: string;
}

export interface HistogramData {
  bins: HistogramBin[];
  mean: number;
  median: number;
  std: number;
}

// ============================================================================
// Warning Heatmap Data
// ============================================================================

export interface WarningHeatmapCell {
  ring_number: number;
  indicator: string;
  level: 'ATTENTION' | 'WARNING' | 'ALARM' | null;
  count: number;
}

export interface WarningHeatmapData {
  cells: WarningHeatmapCell[];
  indicators: string[];
  ringRange: [number, number];
}

// ============================================================================
// Gauge Chart Data
// ============================================================================

export interface GaugeData {
  value: number;
  min: number;
  max: number;
  unit: string;
  thresholds: {
    attention: number;
    warning: number;
    alarm: number;
  };
}

// ============================================================================
// Comparison Chart Data
// ============================================================================

export interface ComparisonData {
  label: string;
  actual: number;
  predicted?: number;
  target?: number;
  unit: string;
}

// ============================================================================
// Chart Config Types
// ============================================================================

export interface ChartColors {
  primary: string;
  secondary: string;
  attention: string;
  warning: string;
  alarm: string;
  success: string;
  background: string;
  grid: string;
  text: string;
}

export interface ChartTheme {
  colors: ChartColors;
  backgroundColor: string;
  textStyle: {
    color: string;
    fontFamily: string;
  };
  animation: boolean;
}

export interface AxisConfig {
  type: 'value' | 'category' | 'time';
  name?: string;
  min?: number | 'dataMin';
  max?: number | 'dataMax';
  interval?: number;
}

export interface TooltipConfig {
  show: boolean;
  trigger: 'axis' | 'item';
  formatter?: string | ((params: any) => string);
}

export interface LegendConfig {
  show: boolean;
  orient: 'horizontal' | 'vertical';
  left?: string | number;
  top?: string | number;
}
